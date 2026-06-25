-- Migration for PAT-169: Add unique constraint for assets tag within model
-- Required for ON CONFLICT clause in upsert_risk_model procedure

ALTER TABLE threat.assets
ADD CONSTRAINT assets_model_id_tag_unique UNIQUE (model_id, tag);
