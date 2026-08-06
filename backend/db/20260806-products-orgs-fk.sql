-- ============================================
-- Add Foreign Key: products.company -> orgs.name
-- ============================================

-- First, add an org_id column to products table for the foreign key relationship
ALTER TABLE public.products 
ADD COLUMN IF NOT EXISTS org_id BIGINT REFERENCES public.orgs(id) ON DELETE SET NULL;

-- Create index on org_id for efficient lookups
CREATE INDEX IF NOT EXISTS idx_products_org_id ON public.products(org_id);

-- Populate org_id by matching products.company to orgs.name
UPDATE public.products p
SET org_id = o.id
FROM public.orgs o
WHERE p.company = o.name
  AND p.org_id IS NULL;

-- Log the operation
INSERT INTO public.system_log (event, context, created_at)
VALUES (
    'products_org_fk_relationship_created',
    jsonb_build_object(
        'action', 'established foreign key relationship between products and orgs',
        'column', 'products.org_id -> orgs.id',
        'products_with_org_id', (SELECT COUNT(*) FROM public.products WHERE org_id IS NOT NULL),
        'total_products', (SELECT COUNT(*) FROM public.products),
        'timestamp', now()
    ),
    now()
);
