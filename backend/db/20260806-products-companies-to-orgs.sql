-- ============================================
-- Populate orgs table with unique companies from products
-- ============================================

-- Insert unique companies from products table into orgs table
-- Only insert if company name doesn't already exist in orgs
INSERT INTO public.orgs (name, description, content_source, created_at, updated_at)
SELECT DISTINCT 
    p.company,
    'FDA-cleared AI-enabled medical device manufacturer' AS description,
    'fda-devices' AS content_source,
    now() AS created_at,
    now() AS updated_at
FROM public.products p
WHERE p.company IS NOT NULL
  AND p.company != ''
  AND NOT EXISTS (
    SELECT 1 FROM public.orgs o WHERE o.name = p.company
  )
ORDER BY p.company;

-- Log the operation
INSERT INTO public.system_log (event, context, created_at)
VALUES (
    'products_companies_imported_to_orgs',
    jsonb_build_object(
        'action', 'imported FDA device manufacturers from products table',
        'timestamp', now()
    ),
    now()
);
