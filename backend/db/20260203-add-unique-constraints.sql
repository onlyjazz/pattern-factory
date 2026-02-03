-- =========================================================
-- Add unique constraints for model-scoped entities
-- Enables ON CONFLICT DO UPDATE for risk model upserts
-- =========================================================

BEGIN;

-- Threats: unique on (model_id, tag)
ALTER TABLE threat.threats
ADD CONSTRAINT threats_model_tag_unique UNIQUE (model_id, tag);

-- Vulnerabilities: unique on (model_id, name)
ALTER TABLE threat.vulnerabilities
ADD CONSTRAINT vulnerabilities_model_name_unique UNIQUE (model_id, name);

-- Countermeasures: unique on (model_id, name)
ALTER TABLE threat.countermeasures
ADD CONSTRAINT countermeasures_model_name_unique UNIQUE (model_id, name);

-- Asset-threat links: unique on (model_id, asset_id, threat_id)
ALTER TABLE threat.asset_threat
ADD CONSTRAINT asset_threat_model_ids_unique UNIQUE (model_id, asset_id, threat_id);

-- Vulnerability-threat links: unique on (model_id, vulnerability_id, threat_id)
ALTER TABLE threat.vulnerability_threat
ADD CONSTRAINT vulnerability_threat_model_ids_unique UNIQUE (model_id, vulnerability_id, threat_id);

-- Countermeasure-threat links: unique on (model_id, countermeasure_id, threat_id)
ALTER TABLE threat.countermeasure_threat
ADD CONSTRAINT countermeasure_threat_model_ids_unique UNIQUE (model_id, countermeasure_id, threat_id);

COMMIT;
