-- ============================================
-- Standardize story field naming
-- ============================================
-- Rename story_md to story in patterns table
ALTER TABLE patterns
RENAME COLUMN story_md TO story;

-- Rename markdown to story in cards table
ALTER TABLE cards
RENAME COLUMN markdown TO story;
