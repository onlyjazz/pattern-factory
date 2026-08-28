-- PAT-330: Threat Classification with Countermeasure Classes
-- Creates countermeasure_class taxonomy and threat_countermeasure_classes junction table

BEGIN;

-- Create countermeasure_class taxonomy table
CREATE TABLE threat.countermeasure_class (
    id SERIAL PRIMARY KEY,
    class TEXT NOT NULL,
    tag TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    CONSTRAINT countermeasure_class_class_unique UNIQUE(class),
    CONSTRAINT countermeasure_class_tag_unique UNIQUE(tag)
);

-- Index for tag lookups
CREATE INDEX idx_countermeasure_class_tag ON threat.countermeasure_class(tag);

-- Add class_id FK to countermeasures (nullable initially, will be populated)
ALTER TABLE threat.countermeasures
ADD COLUMN class_id INTEGER;

-- Add FK constraint after countermeasures populates (deferred constraint or add after load)
ALTER TABLE threat.countermeasures
ADD CONSTRAINT countermeasures_class_id_fkey 
  FOREIGN KEY (class_id) REFERENCES threat.countermeasure_class(id) ON DELETE SET NULL;

-- Create junction table: threat ↔ countermeasure_class (many-to-many)
CREATE TABLE threat.threat_countermeasure_classes (
    id SERIAL PRIMARY KEY,
    threat_id INTEGER NOT NULL REFERENCES threat.threats(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES threat.countermeasure_class(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    CONSTRAINT threat_countermeasure_classes_unique UNIQUE(threat_id, class_id)
);

-- Index for threat lookup
CREATE INDEX idx_threat_countermeasure_classes_threat ON threat.threat_countermeasure_classes(threat_id);

-- Index for class lookup
CREATE INDEX idx_threat_countermeasure_classes_class ON threat.threat_countermeasure_classes(class_id);

-- Version tracking
COMMENT ON TABLE threat.countermeasure_class IS 'Taxonomy of countermeasure control types (e.g., Patient Safety, Clinical Decision Controls)';
COMMENT ON TABLE threat.threat_countermeasure_classes IS 'Multi-class assignment of threats to countermeasure control types';

COMMIT;
