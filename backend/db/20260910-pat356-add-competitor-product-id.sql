-- Add competitor_product_id to competitors table
-- This column stores the product ID of the competitor device (if it exists in products table)

ALTER TABLE public.competitors
ADD COLUMN competitor_product_id BIGINT REFERENCES public.products(id) ON DELETE SET NULL;

-- Create index for competitor product lookups
CREATE INDEX IF NOT EXISTS idx_competitors_competitor_product_id 
ON public.competitors(competitor_product_id) 
WHERE deleted_at IS NULL;
