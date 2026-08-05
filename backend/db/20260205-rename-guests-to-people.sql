-- ============================================
-- Migration: Rename guests table to people
-- ============================================
-- Renames the guests table to people to support
-- more generic content sources (FDA devices, etc.)
-- along with the existing newsletter/substack sources

-- Rename the guests table
ALTER TABLE guests RENAME TO people;

-- Rename the constraint
ALTER TABLE people RENAME CONSTRAINT guests_name_unique TO people_name_unique;

-- Rename the junction table
ALTER TABLE pattern_guest_link RENAME TO pattern_people_link;

-- Rename the foreign key constraints in the junction table
ALTER TABLE pattern_people_link DROP CONSTRAINT pattern_guest_link_guest_id_fkey;
ALTER TABLE pattern_people_link RENAME COLUMN guest_id TO people_id;
ALTER TABLE pattern_people_link ADD CONSTRAINT pattern_people_link_people_id_fkey 
  FOREIGN KEY (people_id) REFERENCES people(id) ON DELETE CASCADE;

-- Rename the index
ALTER INDEX idx_pattern_guest_link_guest RENAME TO idx_pattern_people_link_people;

-- Update the index to reference the new column name
DROP INDEX idx_pattern_people_link_people;
CREATE INDEX idx_pattern_people_link_people ON pattern_people_link(people_id);

-- Rename the search vector index
ALTER INDEX idx_guests_vector RENAME TO idx_people_vector;

-- Update the primary key constraint name if needed
ALTER TABLE pattern_people_link DROP CONSTRAINT pattern_guest_link_pkey;
ALTER TABLE pattern_people_link ADD PRIMARY KEY (pattern_id, people_id);
