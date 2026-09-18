-- Migration: Add portfolio column to orgs table
-- Purpose: Store FDA-cleared device portfolios discovered via Exa agent
-- Structure: {items: [{company, device, intended_use, device_description, primary_product_code, panel, submission_number, submission_type}, ...]}

ALTER TABLE public.orgs
ADD COLUMN IF NOT EXISTS portfolio JSONB DEFAULT NULL;

-- Index for portfolio queries (optional, for future lookups)
CREATE INDEX IF NOT EXISTS idx_orgs_portfolio ON public.orgs USING GIN (portfolio);
