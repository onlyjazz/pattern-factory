/*
 * PAT-371: recompute asset SLE when the organization valuation changes.
 *
 * threat.assets.sle_value is materialized from the organization valuation:
 *
 *   sle_value = orgs.size * asset_valuation.valuation_percentage / 100
 *
 * Historically this was a one-off backfill (see
 * 20260902-pat-315-load-asset-class-and-asset-threat.sql). Nothing recomputed
 * the value when public.orgs.size changed, so threat impact (and therefore the
 * model-risk and enterprise-risk views) kept reporting a stale valuation.
 *
 * This migration:
 *   1. Persists the asset valuation percentages in threat.asset_valuation.
 *   2. Adds threat.recompute_asset_sle_values(org_id) to (re)calculate SLE.
 *   3. Recomputes assets whenever public.orgs.size changes (trigger).
 *   4. Keeps public.orgs.size/tier in sync on UPDATE: an explicit size (e.g. a
 *      post-IPO valuation) takes precedence, otherwise size/tier are derived
 *      from sales/funding. Previously only INSERT was covered.
 *   5. Backfills every existing asset row once.
 *
 * Run with psql:
 *
 *   psql pattern-factory \
 *     -f backend/db/20260924-pat-371-recompute-asset-sle-on-valuation-change.sql
 *
 * Requires jq and base64 on the machine running psql and
 * backend/db/taxonomy-assets-v3.json.
 */

\set ON_ERROR_STOP on

BEGIN;


/* -------------------------------------------------------------------------
 * 1. Persist the asset valuation basis.
 *
 * taxonomy-assets-v3.json is the source of truth for the per-asset valuation
 * percentage (A1..A8 sum to 100%).
 * ------------------------------------------------------------------------- */
CREATE TABLE IF NOT EXISTS threat.asset_valuation (
    asset_tag TEXT PRIMARY KEY,
    valuation_percentage NUMERIC NOT NULL CHECK (
        valuation_percentage >= 0 AND valuation_percentage <= 100
    )
);

CREATE TEMP TABLE _asset_valuation_source (
    payload_base64 TEXT NOT NULL
) ON COMMIT DROP;

\copy _asset_valuation_source(payload_base64) FROM PROGRAM 'jq -c . "/Users/dl/code/pattern-factory/backend/db/taxonomy-assets-v3.json" | base64 | tr -d "\n"'

INSERT INTO threat.asset_valuation (asset_tag, valuation_percentage)
SELECT
    asset.value ->> 'id' AS asset_tag,
    (asset.value ->> 'valuation_percentage')::NUMERIC AS valuation_percentage
FROM _asset_valuation_source source
CROSS JOIN LATERAL jsonb_array_elements(
    (
        convert_from(
            decode(source.payload_base64, 'base64'),
            'UTF8'
        )::JSONB
    ) -> 'assets'
) AS asset(value)
ON CONFLICT (asset_tag)
DO UPDATE
SET valuation_percentage = EXCLUDED.valuation_percentage;


/* -------------------------------------------------------------------------
 * 2. Recompute function.
 *
 * sle_value = orgs.size * valuation_percentage / 100 for every taxonomy asset
 * (tag present in threat.asset_valuation) of the models owned by the org.
 *
 * Called with an organization id it scopes to that organization; called with no
 * argument it recomputes every model (backfill / repair).
 * ------------------------------------------------------------------------- */
CREATE OR REPLACE FUNCTION threat.recompute_asset_sle_values(
    p_org_id BIGINT DEFAULT NULL
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    WITH target AS (
        SELECT
            a.id,
            ROUND(
                COALESCE(org.size, 0)::NUMERIC
                * valuation.valuation_percentage
                / 100.0,
                2
            ) AS new_sle_value
        FROM threat.assets a
        INNER JOIN threat.asset_valuation valuation
            ON valuation.asset_tag = a.tag
        INNER JOIN threat.models model
            ON model.id = a.model_id
        LEFT JOIN public.products product
            ON product.id = model.product_id
        LEFT JOIN public.orgs org
            ON org.id = product.org_id
        WHERE p_org_id IS NULL
           OR org.id = p_org_id
    )
    UPDATE threat.assets asset
    SET sle_value = target.new_sle_value
    FROM target
    WHERE asset.id = target.id
      AND asset.sle_value IS DISTINCT FROM target.new_sle_value;

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated;
END;
$$;


/* -------------------------------------------------------------------------
 * 3. Keep public.orgs.size/tier in sync on UPDATE, letting an explicitly
 *    provided valuation take precedence over the sales/funding rule of thumb.
 *
 * The original trigger was BEFORE INSERT only, so editing sales or funding
 * never refreshed size/tier. On UPDATE:
 *
 *   - if the statement supplies size, that valuation wins (even when it equals
 *     the stored value, as a CRUD form round-tripping the field would send)
 *     and tier is derived from it;
 *   - otherwise size/tier are derived from estimated_annual_sales and funding.
 *
 * Whether size was supplied is detected from the UPDATE target list, not from
 * the value: trg_org_size_a_explicit sets a transaction-local flag and
 * trg_org_size_b_derive consumes it. PostgreSQL fires same-event triggers in
 * alphabetical order, so "a" runs before "b"; trg_org_size_z_clear clears any
 * leftover flag after the statement.
 * ------------------------------------------------------------------------- */
CREATE OR REPLACE FUNCTION public.tier_for_size(p_size BIGINT)
RETURNS BIGINT
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN COALESCE(p_size, 0) > 500000000 THEN 1  -- > $500M
        WHEN COALESCE(p_size, 0) >= 50000000 THEN 2  -- $50M-$500M
        ELSE 3                                        -- < $50M
    END;
$$;

/* Reuse tier_for_size so the thresholds live in one place. */
CREATE OR REPLACE FUNCTION public.compute_org_size_and_tier(
    p_estimated_annual_sales NUMERIC,
    p_funding NUMERIC
)
RETURNS TABLE(computed_size BIGINT, computed_tier BIGINT)
LANGUAGE plpgsql
IMMUTABLE
AS $function$
BEGIN
    computed_size := GREATEST(
        (5 * COALESCE(p_estimated_annual_sales, 0))::BIGINT,
        (10 * COALESCE(p_funding, 0))::BIGINT
    );

    computed_tier := public.tier_for_size(computed_size);

    RETURN NEXT;
END;
$function$;

CREATE OR REPLACE FUNCTION public.mark_org_size_explicit_on_update()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    /* Size was supplied by the statement: keep it and derive tier from it. */
    PERFORM set_config('pattern_factory.org_size_explicit', '1', true);
    NEW.tier := public.tier_for_size(NEW.size);
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.derive_org_size_on_update()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF current_setting('pattern_factory.org_size_explicit', true) = '1' THEN
        /* An explicitly supplied size won for this row; keep it, refresh tier. */
        PERFORM set_config('pattern_factory.org_size_explicit', '', true);
        NEW.tier := public.tier_for_size(NEW.size);
        RETURN NEW;
    END IF;

    IF NEW.estimated_annual_sales IS DISTINCT FROM OLD.estimated_annual_sales
       OR NEW.funding IS DISTINCT FROM OLD.funding THEN
        SELECT computed_size, computed_tier
        INTO NEW.size, NEW.tier
        FROM public.compute_org_size_and_tier(
            NEW.estimated_annual_sales,
            NEW.funding
        );
    ELSE
        /* Size is unchanged: keep it and just keep tier consistent with it. */
        NEW.tier := public.tier_for_size(NEW.size);
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.clear_org_size_explicit_flag()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM set_config('pattern_factory.org_size_explicit', '', true);
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_compute_size_update ON public.orgs;
DROP TRIGGER IF EXISTS trg_org_size_a_explicit ON public.orgs;
DROP TRIGGER IF EXISTS trg_org_size_b_derive ON public.orgs;
DROP TRIGGER IF EXISTS trg_org_size_z_clear ON public.orgs;

CREATE TRIGGER trg_org_size_a_explicit
BEFORE UPDATE OF size ON public.orgs
FOR EACH ROW
EXECUTE FUNCTION public.mark_org_size_explicit_on_update();

CREATE TRIGGER trg_org_size_b_derive
BEFORE UPDATE ON public.orgs
FOR EACH ROW
EXECUTE FUNCTION public.derive_org_size_on_update();

CREATE TRIGGER trg_org_size_z_clear
AFTER UPDATE ON public.orgs
FOR EACH STATEMENT
EXECUTE FUNCTION public.clear_org_size_explicit_flag();

DROP FUNCTION IF EXISTS public.update_org_size_and_tier_on_update();


/* -------------------------------------------------------------------------
 * 4. Recompute asset SLE whenever the organization valuation changes.
 *
 * The trigger deliberately fires on every UPDATE and guards on NEW.size rather
 * than using "AFTER UPDATE OF size": size may change without being a statement
 * target (the BEFORE trigger in section 3 derives it from sales/funding), so an
 * "OF size" clause would miss those updates.
 * ------------------------------------------------------------------------- */
CREATE OR REPLACE FUNCTION public.recompute_asset_sle_on_org_size_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.size IS DISTINCT FROM OLD.size THEN
        PERFORM threat.recompute_asset_sle_values(NEW.id);
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_recompute_asset_sle ON public.orgs;
CREATE TRIGGER trg_recompute_asset_sle
AFTER UPDATE ON public.orgs
FOR EACH ROW
EXECUTE FUNCTION public.recompute_asset_sle_on_org_size_change();


/* -------------------------------------------------------------------------
 * 5. One-time backfill: recompute every asset row and align tiers to the
 *    current valuation.
 * ------------------------------------------------------------------------- */
SELECT threat.recompute_asset_sle_values() AS assets_updated;

SELECT
    COUNT(*) AS tiers_realigned
FROM public.orgs
WHERE tier IS DISTINCT FROM public.tier_for_size(size);

UPDATE public.orgs
SET tier = public.tier_for_size(size)
WHERE tier IS DISTINCT FROM public.tier_for_size(size);

SELECT
    COUNT(*) AS tiers_remaining_inconsistent
FROM public.orgs
WHERE tier IS DISTINCT FROM public.tier_for_size(size);


/* -------------------------------------------------------------------------
 * 6. Validation: no taxonomy asset should disagree with size * percentage.
 * ------------------------------------------------------------------------- */
SELECT
    COUNT(*) AS mismatched_assets
FROM (
    SELECT
        a.sle_value,
        ROUND(
            COALESCE(org.size, 0)::NUMERIC
            * valuation.valuation_percentage
            / 100.0,
            2
        ) AS expected_sle_value
    FROM threat.assets a
    INNER JOIN threat.asset_valuation valuation
        ON valuation.asset_tag = a.tag
    INNER JOIN threat.models model
        ON model.id = a.model_id
    LEFT JOIN public.products product
        ON product.id = model.product_id
    LEFT JOIN public.orgs org
        ON org.id = product.org_id
) check_rows
WHERE sle_value IS DISTINCT FROM expected_sle_value;

COMMIT;
