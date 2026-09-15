-- ============================================
-- Product Competitors Table
-- ============================================
-- Stores relationships between products and their top competing products.
-- Denormalized: company_id is the product owner, competitor_id is the competing org.

CREATE TABLE IF NOT EXISTS public.competitors (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT NOT NULL REFERENCES public.orgs(id) ON DELETE CASCADE,
    competitor_id BIGINT NOT NULL REFERENCES public.orgs(id) ON DELETE CASCADE,
    product_id BIGINT REFERENCES public.products(id) ON DELETE CASCADE,
    rank INT CHECK (rank >= 1 AND rank <= 3),  -- Top 3 competitors only
    rationale TEXT,  -- Brief explanation why this is a competing product
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now(),
    deleted_at TIMESTAMP,
    UNIQUE(company_id, competitor_id, product_id)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_competitors_company_id ON public.competitors(company_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_competitors_competitor_id ON public.competitors(competitor_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_competitors_product_id ON public.competitors(product_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_competitors_rank ON public.competitors(rank) WHERE deleted_at IS NULL;

-- Add trigger to update updated_at
CREATE OR REPLACE TRIGGER update_competitors_updated_at
BEFORE UPDATE ON public.competitors
FOR EACH ROW
EXECUTE PROCEDURE public.update_updated_at_column();
