-- ============================================
-- Migration: Add estimated_annual_sales to orgs
-- ============================================
-- Adds a numeric column to track estimated annual sales for organizations

ALTER TABLE orgs
ADD COLUMN estimated_annual_sales NUMERIC;
