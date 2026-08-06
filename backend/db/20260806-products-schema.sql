-- ============================================
-- FDA AI-Enabled Medical Devices Products Table
-- ============================================

-- Create products table in public schema
DROP TABLE IF EXISTS public.products CASCADE;
CREATE TABLE public.products (
    id BIGSERIAL PRIMARY KEY,
    date_of_final_decision TIMESTAMP,
    submission_number TEXT NOT NULL UNIQUE,
    device TEXT NOT NULL,
    indicated_use TEXT,
    company TEXT,
    panel TEXT,
    primary_product_code TEXT,
    product_contact_1 TEXT,          -- LinkedIn profile URL
    product_contact_2 TEXT,          -- LinkedIn profile URL
    product_contact_3 TEXT,          -- LinkedIn profile URL
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX idx_products_submission_number ON public.products(submission_number);
CREATE INDEX idx_products_company ON public.products(company);
CREATE INDEX idx_products_active ON public.products(id) WHERE deleted_at IS NULL;

-- Add foreign key relationships
-- Link products to orgs by company name (company field matches orgs.name)
-- This will be enforced at application level during batch load

-- Add trigger to update updated_at
CREATE OR REPLACE TRIGGER update_products_updated_at
BEFORE UPDATE ON public.products
FOR EACH ROW
EXECUTE PROCEDURE public.update_updated_at_column();

-- Add company field to threat.models if not exists (for product-to-model linking)
-- Models can specify which product company they belong to via submission_number
ALTER TABLE threat.models ADD COLUMN IF NOT EXISTS submission_number TEXT;
CREATE INDEX IF NOT EXISTS idx_models_submission_number ON threat.models(submission_number);

-- Add full-text search index for products
CREATE OR REPLACE FUNCTION products_vector_update() RETURNS trigger AS $$
BEGIN
  NEW.search_vector :=
    to_tsvector('english', coalesce(NEW.device,'') || ' ' || coalesce(NEW.indicated_use,'') || ' ' || coalesce(NEW.company,''));
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

ALTER TABLE public.products ADD COLUMN IF NOT EXISTS search_vector tsvector;
DROP INDEX IF EXISTS idx_products_vector CASCADE;
CREATE INDEX idx_products_vector ON public.products USING GIN (search_vector);

CREATE OR REPLACE TRIGGER trg_products_vector_update
BEFORE INSERT OR UPDATE ON public.products
FOR EACH ROW EXECUTE FUNCTION products_vector_update();
