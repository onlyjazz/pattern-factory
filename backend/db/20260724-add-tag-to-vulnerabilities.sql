-- =========================================================
-- Pattern Factory — Add tag column to vulnerabilities table
-- Date: 2026-07-24
-- Purpose: Allow vulnerabilities to have unique short identifiers
--          similar to threats and other entities
-- =========================================================

BEGIN;

-- Add tag column to vulnerabilities table with DEFAULT value
ALTER TABLE threat.vulnerabilities
ADD COLUMN tag VARCHAR(50) DEFAULT ('V' || id);

-- Populate tag with V+id format for existing rows (e.g., V255 for id=255)
UPDATE threat.vulnerabilities
SET tag = 'V' || id
WHERE tag IS NULL;

-- Add NOT NULL constraint
ALTER TABLE threat.vulnerabilities
ALTER COLUMN tag SET NOT NULL;

-- Create unique constraint on (model_id, tag) to ensure uniqueness per model
ALTER TABLE threat.vulnerabilities
ADD CONSTRAINT vulnerabilities_model_tag_unique UNIQUE (model_id, tag);

COMMIT;
