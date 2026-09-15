-- PAT-356: Add competitors column to products table
-- This column stores a comma-separated list of competitor product names
-- for easy integration with Close CRM

ALTER TABLE public.products
ADD COLUMN IF NOT EXISTS competitors TEXT;

-- Create a function to populate competitors column from the competitors table
CREATE OR REPLACE FUNCTION update_product_competitors()
RETURNS TRIGGER AS $$
DECLARE
  competitor_list TEXT;
BEGIN
  -- Get comma-separated list of competitor products for this product
  SELECT string_agg(p.device, ', ' ORDER BY c.rank)
  INTO competitor_list
  FROM public.competitors c
  JOIN public.products p ON c.competitor_product_id = p.id
  WHERE c.product_id = NEW.product_id
    AND c.competitor_product_id IS NOT NULL;
  
  -- Update the competitors column on the products table
  UPDATE public.products
  SET competitors = competitor_list
  WHERE id = NEW.product_id;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to update competitors column when competitors table is modified
DROP TRIGGER IF EXISTS trg_update_product_competitors ON public.competitors;
CREATE TRIGGER trg_update_product_competitors
AFTER INSERT OR UPDATE OR DELETE ON public.competitors
FOR EACH ROW
EXECUTE FUNCTION update_product_competitors();

-- Backfill existing products with competitors
UPDATE public.products p
SET competitors = (
  SELECT string_agg(prod.device, ', ' ORDER BY c.rank)
  FROM public.competitors c
  JOIN public.products prod ON c.competitor_product_id = prod.id
  WHERE c.product_id = p.id
    AND c.competitor_product_id IS NOT NULL
)
WHERE EXISTS (
  SELECT 1 FROM public.competitors c
  WHERE c.product_id = p.id AND c.competitor_product_id IS NOT NULL
);
