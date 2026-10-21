/*
 * PAT-398: set up an experiment scenario on public.products.
 *
 * An experiment selects its products by products.tag, and the Close hand-off
 * reads products.sle_after_mitigation. Setting up a scenario therefore means
 * stamping both, for every product whose model carries the scenario's threat:
 *
 *   SELECT * FROM public.apply_experiment_scenario('<exact threat name>', '<tag>');
 *
 * The SLE comes from threat.threat_impact(model_id) -- the PAT-399 per-model
 * implementation, reached through threat.models.product_id -- rather than a
 * re-derivation of the mitigation arithmetic, so the figure reconciles with
 * public.product_sle_after_mitigation and public."THRIM".
 *
 * The function returns one row per product it changed, with the before/after
 * SLE, so a run is its own audit trail; re-running it returns no rows. The tag
 * is then the durable record of the experiment's membership:
 *
 *   SELECT id, device, tag, sle_after_mitigation FROM public.products
 *   WHERE tag = 'Experiment 1' AND deleted_at IS NULL ORDER BY id;
 *
 * Matching is exact and case-sensitive against threat.threats.name. The
 * catalogue holds deliberate near-misses that an exact match excludes, e.g.
 * 'Patient-Study Misassociation', 'Patient-study-misassociation' and
 * 'Study-patient misassociation'. Confirm the spelling first:
 *
 *   SELECT name, count(*) FROM threat.threats
 *   WHERE name ILIKE '%<fragment>%' GROUP BY name ORDER BY 2 DESC;
 *
 * Notes and caveats:
 *   - sle_after_mitigation normally holds the product's all-threat total
 *     (backfilled from public.product_sle_after_mitigation). This overrides it
 *     with the scenario's figure for the tagged products, so the column is
 *     scenario-scoped for that set. Re-running
 *     20261020-pat-398-products-tag-sle-after-mitigation.sql restores the
 *     totals and undoes the override.
 *   - tag is overwritten, so a product already assigned to another experiment
 *     moves to this one. Nothing else is cleared.
 *   - A threat only contributes if threat.threat_impact emits it: the threat
 *     and its assets must be enabled and it must link at least one A1-A8 core
 *     asset. Products whose named threat is not emitted are left untouched.
 *   - Soft-deleted products (products.deleted_at IS NOT NULL) are skipped.
 *   - If a model ever carried several threats with the same name, the greatest
 *     sle_after_mitigation of them wins, so the result is deterministic rather
 *     than dependent on row order.
 *
 * Verify after running (a second run reports 0):
 *
 *   SELECT count(*) FROM public.products
 *   WHERE tag = 'Experiment 1' AND deleted_at IS NULL;   -- 187
 *
 * Run with psql:
 *
 *   psql pattern-factory \
 *     -f backend/db/20261020-pat-398-experiment-scenario-setup.sql
 */

\set ON_ERROR_STOP on

BEGIN;


/* -------------------------------------------------------------------------
 * 0. Supersede the SLE-only helper from the first cut of this work.
 *
 * It set sle_after_mitigation but left tag untouched, which would leave the
 * experiment unable to select its products. apply_experiment_scenario() below
 * replaces it.
 * ------------------------------------------------------------------------- */
DROP FUNCTION IF EXISTS public.set_product_sle_from_threat(TEXT);


/* -------------------------------------------------------------------------
 * 1. Scenario setup.
 *
 * The product is reached through threat.models.product_id (one model per
 * product). The threat.threats join narrows the LATERAL to the models that
 * actually carry the name, instead of calling threat_impact once per model.
 *
 * Only rows whose SLE or tag would actually change are updated and returned,
 * which is what makes the function idempotent and its output a run's audit
 * trail. The CTE aliases are prefixed so they cannot be confused with the
 * function's OUT parameter names.
 * ------------------------------------------------------------------------- */
CREATE OR REPLACE FUNCTION public.apply_experiment_scenario(
    p_threat_name TEXT,
    p_tag TEXT
)
RETURNS TABLE (
    product_id BIGINT,
    device TEXT,
    previous_sle NUMERIC,
    new_sle NUMERIC,
    tag TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_tag IS NULL OR btrim(p_tag) = '' THEN
        RAISE EXCEPTION 'p_tag must be a non-empty experiment label';
    END IF;

    RETURN QUERY
    WITH threat_sle AS (
        SELECT
            model.product_id,
            MAX(impact.sle_after_mitigation)::NUMERIC AS scenario_sle
        FROM threat.models model
        INNER JOIN threat.threats named_threat
            ON named_threat.model_id = model.id
           AND named_threat.name = p_threat_name
        CROSS JOIN LATERAL threat.threat_impact(model.id::INTEGER) impact
        WHERE impact.threat_name = p_threat_name
        GROUP BY model.product_id
    ),
    target AS (
        SELECT
            product.id AS target_id,
            product.device AS target_device,
            product.sle_after_mitigation AS target_previous_sle,
            threat_sle.scenario_sle AS target_new_sle
        FROM public.products product
        INNER JOIN threat_sle
            ON threat_sle.product_id = product.id
        WHERE product.deleted_at IS NULL
          AND (
              product.sle_after_mitigation IS DISTINCT FROM threat_sle.scenario_sle
              OR product.tag IS DISTINCT FROM p_tag
          )
    )
    UPDATE public.products product
    SET sle_after_mitigation = target.target_new_sle,
        tag = p_tag
    FROM target
    WHERE product.id = target.target_id
    RETURNING
        product.id,
        target.target_device,
        target.target_previous_sle,
        product.sle_after_mitigation,
        product.tag;
END;
$$;

COMMENT ON FUNCTION public.apply_experiment_scenario(TEXT, TEXT) IS
    'Stamp public.products for one experiment scenario: sle_after_mitigation from the named threat (threat.threat_impact) plus tag from p_tag, for every product whose model carries that threat. Returns one row per product changed (with before/after SLE); idempotent.';


/* -------------------------------------------------------------------------
 * 2. Apply it to experiment 1.
 *
 * 187 products carry the threat. The first run changes all 187 (180 SLE values
 * plus 7 tag-only, where the scenario figure and the total were both 0); every
 * run after that returns no rows.
 * ------------------------------------------------------------------------- */
SELECT count(*) AS products_updated
FROM public.apply_experiment_scenario('Patient-study misassociation', 'Experiment 1');


COMMIT;
