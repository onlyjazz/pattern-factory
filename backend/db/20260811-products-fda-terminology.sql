-- ============================================
-- FDA Terminology Correction: Split indicated_use into intended_use and indications_for_use
-- ============================================
-- Intended Use: The general function or purpose of the device as claimed by manufacturer
-- Indications for Use: The specific medical conditions or diseases the device treats/diagnoses
-- Reference: https://www.elexes.com/intended-use-and-indications-for-use/

-- Step 1: Add new columns
ALTER TABLE public.products
ADD COLUMN IF NOT EXISTS intended_use TEXT;

ALTER TABLE public.products
ADD COLUMN IF NOT EXISTS indications_for_use TEXT;

-- Step 2: Migrate data from indicated_use to intended_use (general purpose)
-- Indications_for_use will be populated by FDA Primary Source service later
UPDATE public.products
SET intended_use = indicated_use
WHERE indicated_use IS NOT NULL AND intended_use IS NULL;

-- Step 3: (removed) products full-text search was dropped — search_vector and
-- products_vector_update() no longer exist, so there is nothing to update or
-- rebuild here.

-- Step 5: Drop old indicated_use column (after successful migration)
-- Keeping the old column for now to avoid data loss during testing
-- ALTER TABLE public.products DROP COLUMN IF EXISTS indicated_use;

-- Step 6: Create index on new columns for query performance
CREATE INDEX IF NOT EXISTS idx_products_intended_use ON public.products(intended_use);
CREATE INDEX IF NOT EXISTS idx_products_indications_for_use ON public.products(indications_for_use);

-- Step 7: Log migration
INSERT INTO public.system_log (event, context)
VALUES (
    'SCHEMA_MIGRATION',
    jsonb_build_object(
        'migration', '20260811-products-fda-terminology',
        'description', 'Split indicated_use into intended_use (general purpose) and indications_for_use (specific conditions)',
        'timestamp', now(),
        'reference', 'https://www.elexes.com/intended-use-and-indications-for-use/'
    )
) ON CONFLICT DO NOTHING;
