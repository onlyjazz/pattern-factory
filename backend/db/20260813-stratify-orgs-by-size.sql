-- =========================================================
-- Pattern Factory — Stratify Organizations by Market Size
-- Date: 2026-08-13
-- Purpose: Add size and tier columns to segment ~1,500 FDA
--          medical device manufacturers by strategic positioning.
--          Tier 1: Enterprise (>$500M), Tier 2: Mid-Market ($50M–$500M),
--          Tier 3: Startup (<$50M)
-- =========================================================

BEGIN;

-- =========================================================
-- Add size column (computed metric)
-- =========================================================
-- size = GREATEST(5 * estimated_annual_sales, 10 * funding)
-- Captures relative scale: 5x revenue or 10x funding amount
--
ALTER TABLE public.orgs
ADD COLUMN size BIGINT DEFAULT 0 NOT NULL;

-- =========================================================
-- Add tier column (stratification)
-- =========================================================
-- Tier 1: size > 500M (Enterprise Strategic Players)
-- Tier 2: size 50M–500M (Mid-Market Challengers)
-- Tier 3: size < 50M (Pure-Play AI Startups)
--
ALTER TABLE public.orgs
ADD COLUMN tier BIGINT DEFAULT 3 NOT NULL;

-- =========================================================
-- Create function to compute size and tier
-- =========================================================
CREATE OR REPLACE FUNCTION public.compute_org_size_and_tier(
    p_estimated_annual_sales NUMERIC,
    p_funding NUMERIC
) RETURNS TABLE (
    computed_size BIGINT,
    computed_tier BIGINT
) AS $$
BEGIN
    -- Compute size as the maximum of:
    -- - 5 times estimated annual sales
    -- - 10 times funding amount
    computed_size := GREATEST(
        (5 * COALESCE(p_estimated_annual_sales, 0))::BIGINT,
        (10 * COALESCE(p_funding, 0))::BIGINT
    );
    
    -- Assign tier based on size thresholds
    computed_tier := CASE
        WHEN computed_size > 500000000 THEN 1  -- > $500M
        WHEN computed_size >= 50000000 THEN 2   -- $50M–$500M
        ELSE 3                                   -- < $50M
    END;
    
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =========================================================
-- Backfill size and tier for all existing organizations
-- =========================================================
UPDATE public.orgs o
SET
    size = (SELECT computed_size FROM public.compute_org_size_and_tier(
        o.estimated_annual_sales, o.funding
    )),
    tier = (SELECT computed_tier FROM public.compute_org_size_and_tier(
        o.estimated_annual_sales, o.funding
    ));

-- =========================================================
-- Create trigger to auto-compute size and tier on insert/update
-- =========================================================
CREATE OR REPLACE FUNCTION public.update_org_size_and_tier()
RETURNS TRIGGER AS $$
BEGIN
    -- Recompute whenever estimated_annual_sales or funding change
    SELECT computed_size, computed_tier
    INTO NEW.size, NEW.tier
    FROM public.compute_org_size_and_tier(
        NEW.estimated_annual_sales,
        NEW.funding
    );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_org_size_and_tier ON public.orgs;
CREATE TRIGGER trg_org_size_and_tier
BEFORE INSERT OR UPDATE ON public.orgs
FOR EACH ROW
EXECUTE FUNCTION public.update_org_size_and_tier();

-- =========================================================
-- Verification queries (for testing)
-- =========================================================
/*
-- Check distribution across tiers
SELECT
    tier,
    COUNT(*) AS org_count,
    MIN(size) AS min_size,
    MAX(size) AS max_size,
    ROUND(AVG(size)::NUMERIC, 0) AS avg_size
FROM public.orgs
WHERE deleted_at IS NULL
GROUP BY tier
ORDER BY tier;

-- Sample Tier 1 orgs (Strategic)
SELECT
    name,
    estimated_annual_sales,
    funding,
    size,
    tier
FROM public.orgs
WHERE tier = 1 AND deleted_at IS NULL
ORDER BY size DESC
LIMIT 10;

-- Sample Tier 2 orgs (Mid-Market)
SELECT
    name,
    estimated_annual_sales,
    funding,
    size,
    tier
FROM public.orgs
WHERE tier = 2 AND deleted_at IS NULL
ORDER BY size DESC
LIMIT 10;

-- Sample Tier 3 orgs (Startup)
SELECT
    name,
    estimated_annual_sales,
    funding,
    size,
    tier
FROM public.orgs
WHERE tier = 3 AND deleted_at IS NULL
ORDER BY size DESC
LIMIT 10;

-- Verify tier boundaries
SELECT
    CASE WHEN size > 500000000 THEN 'Should be Tier 1' ELSE 'OK' END,
    CASE WHEN size >= 50000000 AND size <= 500000000 THEN 'Should be Tier 2' ELSE 'OK' END,
    CASE WHEN size < 50000000 THEN 'Should be Tier 3' ELSE 'OK' END,
    COUNT(*) AS count
FROM public.orgs
WHERE deleted_at IS NULL
  AND tier NOT IN (
    CASE
        WHEN size > 500000000 THEN 1
        WHEN size >= 50000000 THEN 2
        ELSE 3
    END
  )
GROUP BY tier;
*/

COMMIT;
