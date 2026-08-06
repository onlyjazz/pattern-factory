-- Migration: Add enrichment fields to orgs table
-- Date: 2026-08-06
-- Purpose: Support organization enrichment with employee count and headquarters location

ALTER TABLE public.orgs
ADD COLUMN IF NOT EXISTS employees INTEGER,
ADD COLUMN IF NOT EXISTS headquarters TEXT;

-- Add comment documentation
COMMENT ON COLUMN public.orgs.employees IS 'Number of employees (from enrichment data)';
COMMENT ON COLUMN public.orgs.headquarters IS 'Headquarters location (city, country) from enrichment data';

-- Verify columns exist
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'orgs' AND column_name IN ('employees', 'headquarters')
ORDER BY ordinal_position;
