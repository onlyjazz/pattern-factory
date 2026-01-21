-- Drop scenario column from threat.threats
-- Scenario is now stored in the related card, making this field redundant
ALTER TABLE threat.threats DROP COLUMN scenario;
