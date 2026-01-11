-- Add taxonomy field to patterns table
ALTER TABLE patterns
ADD COLUMN IF NOT EXISTS taxonomy TEXT DEFAULT NULL;
