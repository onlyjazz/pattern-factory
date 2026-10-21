/*
 * PAT-403: scope apply_experiment_scenario() to a single product.
 *
 * The all-products form reports only the rows it changed - that is what keeps it
 * idempotent and stops a no-op run from bumping products.updated_at via the
 * update trigger - so a second run prints no rows and reads as "nothing
 * happened". That makes one product hard to inspect, because you cannot tell
 * "already applied" from "the threat is not emitted for this product".
 *
 * This migration adds an optional p_product_id so the helper can be pointed at a
 * single row:
 *
 *   SELECT * FROM public.apply_experiment_scenario(
 *       'Patient-study misassociation', 'Experiment 1', 880);
 *
 * The 2-argument signature is replaced by this 3-argument one. The new argument
 * defaults to NULL, so existing 2-argument calls keep working unchanged.
 *
 * Semantics:
 *   - p_product_id IS NULL     -> every product whose model carries the threat
 *   - p_product_id IS NOT NULL -> only that product
 *
 * It still returns only the rows it changed. To see what a single product's
 * model yields without writing anything, read the same computation directly:
 *
 *   SELECT impact.threat_name, impact.sle_after_mitigation
 *   FROM public.products product
 *   JOIN threat.models model ON model.product_id = product.id
 *   CROSS JOIN LATERAL threat.threat_impact(model.id::INTEGER) impact
 *   WHERE product.id = 880
 *     AND impact.threat_name = 'Patient-study misassociation';
 *
 * No rows there means the threat is disabled or links no A1-A8 core asset, so
 * the helper will never touch that product. Rows there, with a 0-row helper run,
 * means the product already holds the value.
 *
 * Run with psql:
 *
 *   psql pattern-factory \
 *     -f backend/db/20261021-pat-403-apply-experiment-scenario-product-id.sql
 */

\set ON_ERROR_STOP on

BEGIN;

-- DROP is required: CREATE OR REPLACE cannot change an argument list, it would
-- only add a second overload and leave the old 2-argument form in place.
DROP FUNCTION IF EXISTS public.apply_experiment_scenario(TEXT, TEXT);

CREATE OR REPLACE FUNCTION public.apply_experiment_scenario(
    p_threat_name TEXT,
    p_tag TEXT,
    p_product_id BIGINT DEFAULT NULL
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
          -- Scoping here, rather than in the target CTE, keeps the per-model
          -- function calls down to the one product when an id is supplied.
          AND (p_product_id IS NULL OR model.product_id = p_product_id)
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

COMMENT ON FUNCTION public.apply_experiment_scenario(TEXT, TEXT, BIGINT) IS
    'Stamp public.products for one experiment scenario: sle_after_mitigation from the named threat (threat.threat_impact) plus tag from p_tag, for every product whose model carries that threat - or a single product when p_product_id is supplied. Returns one row per product changed (with before/after SLE); idempotent.';


/* -------------------------------------------------------------------------
 * Smoke tests. Both are no-ops against an already-applied scenario, so they
 * prove the new signature resolves and the defaulted argument still works
 * without touching any data. Both should report 0.
 * ------------------------------------------------------------------------- */
SELECT count(*) AS three_arg_noop
FROM public.apply_experiment_scenario('Patient-study misassociation', 'Experiment 1', 880);

SELECT count(*) AS two_arg_still_resolves
FROM public.apply_experiment_scenario('Patient-study misassociation', 'Experiment 1');


COMMIT;
