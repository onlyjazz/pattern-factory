-- ============================================
-- Add device_description and superiority columns to products table
-- ============================================

-- Add device_description column (populated from OpenFDA)
ALTER TABLE public.products
ADD COLUMN IF NOT EXISTS device_description TEXT;

-- Add superiority column (populated by feelgood agent flow)
ALTER TABLE public.products
ADD COLUMN IF NOT EXISTS superiority TEXT;

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_products_device_description ON public.products(device_description);
CREATE INDEX IF NOT EXISTS idx_products_superiority ON public.products(superiority);

-- Update updated_at trigger to capture changes to new columns
-- (existing trigger should already handle this)

-- Log migration
INSERT INTO public.system_log (event_type, entity_table, entity_id, details)
VALUES (
    'SCHEMA_MIGRATION',
    'products',
    NULL,
    jsonb_build_object(
        'migration', '20260811-add-product-details',
        'description', 'Added device_description and superiority columns to products table',
        'timestamp', now()
    )
) ON CONFLICT DO NOTHING;
