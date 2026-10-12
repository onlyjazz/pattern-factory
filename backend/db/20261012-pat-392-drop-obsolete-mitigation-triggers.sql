-- =========================================================
-- PAT-392: Drop obsolete mitigation_level triggers and helpers
-- Date: 2026-10-12
--
-- Symptom:
--   "generate <card-url>" failed at the final upsert step with
--   'column ti.residual_risk_pct does not exist'
--
-- Cause:
--   20260701-mitigation-level-function.sql installed a trigger suite that kept
--   threat.threats.mitigation_level in sync by calling
--   threat.compute_mitigation_level(), which reads threat.threat_impact.
--   20260902-pat-341-threat-impact-sle-views.sql later replaced
--   threat_impact.residual_risk_pct with current_mitigation_pct /
--   current_residual_exposure_pct / target_mitigation_pct /
--   target_residual_exposure_pct, but the helper was never updated.
--
--   The triggers on threat.threats (trg_insert_threat_mitigation,
--   trg_update_threat_mitigation) have already been dropped, but the two
--   countermeasure-side triggers from the same migration were missed and are
--   still installed. They fire on every countermeasure / countermeasure_threat
--   write — i.e. step 3 and step 6 of upsert_risk_model — and call the stale
--   function, aborting the whole upsert.
--
-- Fix:
--   Residual risk and mitigation are computed on the fly in the threat_impact
--   view (current_mitigation_pct / target_mitigation_pct), so these triggers are
--   obsolete. Drop the two remaining triggers plus the now-dead helper
--   functions that only existed to serve them.
--
-- Note:
--   No view depends on threat.threats.mitigation_level except threat.vthreats
--   (a straight SELECT t.* passthrough), so nothing computed is affected.
--   threats.mitigation_level remains as a stored, manually editable column.
-- =========================================================

BEGIN;

-- Triggers that fire on countermeasure writes (steps 3 and 6 of the upsert)
DROP TRIGGER IF EXISTS trg_countermeasure_threat_mitigation ON threat.countermeasure_threat;
DROP TRIGGER IF EXISTS trg_countermeasure_impl_mitigation ON threat.countermeasures;

-- Defensive: also clear the threat-side triggers in case they are reinstalled
DROP TRIGGER IF EXISTS trg_insert_threat_mitigation ON threat.threats;
DROP TRIGGER IF EXISTS trg_update_threat_mitigation ON threat.threats;

-- Dead helpers (only referenced by the triggers above)
DROP FUNCTION IF EXISTS threat.update_threat_mitigation_on_countermeasure_change();
DROP FUNCTION IF EXISTS threat.update_threat_mitigation_level();

-- Stale: reads threat_impact.residual_risk_pct, which no longer exists
DROP FUNCTION IF EXISTS threat.compute_mitigation_level(integer);

COMMIT;
