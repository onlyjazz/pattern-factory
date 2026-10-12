-- =========================================================
-- PAT-392: Restore unique constraint on threat.threats (model_id, tag)
-- Date: 2026-10-12
--
-- Symptom:
--   "generate <card-url>" failed with
--   "there is no unique or exclusion constraint matching the
--    ON CONFLICT specification"
--
-- Cause:
--   threat.upsert_risk_model upserts threats with
--   ON CONFLICT (model_id, tag), but the unique constraint
--   threats_model_tag_unique was missing from threat.threats
--   in the live database (the other constraints added by
--   20260203-add-unique-constraints.sql were still present).
--
-- This migration re-asserts the constraint idempotently so it is
-- safe to run on databases that already have it.
-- =========================================================

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'threats_model_tag_unique'
          AND conrelid = 'threat.threats'::regclass
    ) THEN
        ALTER TABLE threat.threats
        ADD CONSTRAINT threats_model_tag_unique UNIQUE (model_id, tag);
    END IF;
END $$;

COMMIT;
