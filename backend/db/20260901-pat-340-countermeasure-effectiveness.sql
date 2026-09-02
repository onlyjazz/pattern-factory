-- PAT-340: Add effectiveness tracking to countermeasures
--
-- Adds three new columns to track countermeasure effectiveness and implementation details:
--   - implementation_notes TEXT: Practical notes on implementing the countermeasure
--   - effectiveness TEXT: Description of effectiveness limitations and caveats
--   - mitigation_level INT: Numeric mitigation level (0-100) from taxonomy

ALTER TABLE threat.countermeasures
ADD COLUMN implementation_notes TEXT DEFAULT NULL,
ADD COLUMN effectiveness TEXT DEFAULT NULL,
ADD COLUMN mitigation_level INTEGER DEFAULT NULL;

-- Add CHECK constraint to ensure mitigation_level is within valid range
ALTER TABLE threat.countermeasures
ADD CONSTRAINT countermeasures_mitigation_level_check
CHECK (mitigation_level IS NULL OR (mitigation_level >= 0 AND mitigation_level <= 100));

-- Log migration
INSERT INTO public.system_log (event, context)
VALUES (
    'schema_migration',
    jsonb_build_object(
        'migration', '20260901-pat-340-countermeasure-effectiveness',
        'changes', jsonb_build_object(
            'table', 'threat.countermeasures',
            'added_columns', jsonb_build_array(
                'implementation_notes',
                'effectiveness',
                'mitigation_level'
            )
        )
    )
);
