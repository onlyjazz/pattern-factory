-- Add story_md field to patterns table
ALTER TABLE patterns
ADD COLUMN IF NOT EXISTS story_md TEXT DEFAULT NULL;
