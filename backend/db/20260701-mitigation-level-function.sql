-- =========================================================
-- Pattern Factory — Compute Mitigation Level Function
-- Date: 2026-07-01
-- Purpose: Transparently compute threat.mitigation_level
--          from threat_impact view as residual_risk_pct * 100
-- =========================================================

BEGIN;

-- =========================================================
-- Create function to compute mitigation_level for a threat
-- =========================================================
CREATE OR REPLACE FUNCTION threat.compute_mitigation_level(p_threat_id INTEGER)
RETURNS INTEGER AS $$
BEGIN
    -- Mitigation level = 100 - residual_risk_pct (as an integer).
    --
    -- IMPORTANT: use a scalar subquery wrapped in COALESCE so this function
    -- NEVER returns NULL. The threat_impact view returns NO rows for a threat
    -- that has no asset_threat links, is disabled, or whose model is not the
    -- active model. A plain SELECT ... INTO leaves the target variable NULL in
    -- that zero-rows case, and the inner COALESCE only handles a NULL column
    -- value from a matching row — it does NOT handle "no rows". Writing that
    -- NULL back via the trigger then violates the NOT NULL constraint on
    -- threats.mitigation_level. Wrapping the scalar subquery in COALESCE(..., 0)
    -- yields the fallback when the subquery returns no rows.
    RETURN COALESCE(
        (
            SELECT 100 - ROUND(ti.residual_risk_pct)::INTEGER
            FROM threat.threat_impact ti
            WHERE ti.threat_tag <> 'TOTAL'
              AND ti.threat_tag = (
                SELECT t.tag FROM threat.threats t WHERE t.id = p_threat_id LIMIT 1
              )
            LIMIT 1
        ),
        0
    );
END;
$$ LANGUAGE plpgsql STABLE;

-- =========================================================
-- Create helper function for countermeasure changes FIRST
-- (before it's referenced in triggers)
-- =========================================================
CREATE OR REPLACE FUNCTION threat.update_threat_mitigation_on_countermeasure_change()
RETURNS TRIGGER AS $$
DECLARE
    v_threat_id INTEGER;
BEGIN
    -- Handle both INSERT/UPDATE/DELETE from countermeasure_threat
    -- and UPDATE from countermeasures table
    IF TG_TABLE_NAME = 'countermeasure_threat' THEN
        v_threat_id := COALESCE(NEW.threat_id, OLD.threat_id);
    ELSIF TG_TABLE_NAME = 'countermeasures' THEN
        -- Update all threats that reference this countermeasure
        FOR v_threat_id IN
            SELECT DISTINCT threat_id FROM threat.countermeasure_threat
            WHERE countermeasure_id = COALESCE(NEW.id, OLD.id)
        LOOP
            UPDATE threat.threats
            SET mitigation_level = COALESCE(threat.compute_mitigation_level(v_threat_id), 0)
            WHERE id = v_threat_id;
        END LOOP;
        RETURN COALESCE(NEW, OLD);
    END IF;
    
    -- Update the threat's mitigation level (defensive: never write NULL)
    IF v_threat_id IS NOT NULL THEN
        UPDATE threat.threats
        SET mitigation_level = COALESCE(threat.compute_mitigation_level(v_threat_id), 0)
        WHERE id = v_threat_id;
    END IF;
    
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- =========================================================
-- Create trigger function to automatically update mitigation_level
-- when threat data changes
-- =========================================================
CREATE OR REPLACE FUNCTION threat.update_threat_mitigation_level()
RETURNS TRIGGER AS $$
DECLARE
    v_new_level INTEGER;
BEGIN
    -- Recursion guard: this function issues a nested UPDATE on threat.threats,
    -- which would re-fire the AFTER UPDATE trigger. Skip when re-entered so we
    -- don't loop infinitely. pg_trigger_depth() is 1 for the original fire and
    -- 2+ for the nested UPDATE we issue below.
    IF pg_trigger_depth() > 1 THEN
        RETURN NEW;
    END IF;

    -- compute_mitigation_level is NULL-safe (returns 0 when the threat is
    -- absent from the threat_impact view), but guard defensively so a NULL can
    -- never reach the NOT NULL column.
    v_new_level := threat.compute_mitigation_level(NEW.id);
    IF v_new_level IS NOT NULL THEN
        UPDATE threat.threats
        SET mitigation_level = v_new_level
        WHERE id = NEW.id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger on threat insertion
DROP TRIGGER IF EXISTS trg_insert_threat_mitigation ON threat.threats;
CREATE TRIGGER trg_insert_threat_mitigation
AFTER INSERT ON threat.threats
FOR EACH ROW
EXECUTE FUNCTION threat.update_threat_mitigation_level();

-- Trigger on threat update — fire on EVERY update so mitigation_level is
-- always recomputed (name, tag, domain, card_id, probability, STRIDE,
-- disabled, etc.). The previous WHEN (OLD IS DISTINCT FROM NEW ...) clause
-- was overly restrictive and skipped recompute for many updates.
-- Recursion is prevented inside the function via pg_trigger_depth().
DROP TRIGGER IF EXISTS trg_update_threat_mitigation ON threat.threats;
CREATE TRIGGER trg_update_threat_mitigation
AFTER UPDATE ON threat.threats
FOR EACH ROW
EXECUTE FUNCTION threat.update_threat_mitigation_level();

-- Trigger on countermeasure_threat insert/update/delete
-- (when countermeasure mitigation levels change)
DROP TRIGGER IF EXISTS trg_countermeasure_threat_mitigation ON threat.countermeasure_threat;
CREATE TRIGGER trg_countermeasure_threat_mitigation
AFTER INSERT OR UPDATE OR DELETE ON threat.countermeasure_threat
FOR EACH ROW
EXECUTE FUNCTION threat.update_threat_mitigation_on_countermeasure_change();

-- Trigger on countermeasure implementation status change
DROP TRIGGER IF EXISTS trg_countermeasure_impl_mitigation ON threat.countermeasures;
CREATE TRIGGER trg_countermeasure_impl_mitigation
AFTER UPDATE ON threat.countermeasures
FOR EACH ROW
WHEN (
    OLD.implemented IS DISTINCT FROM NEW.implemented OR
    OLD.disabled IS DISTINCT FROM NEW.disabled
)
EXECUTE FUNCTION threat.update_threat_mitigation_on_countermeasure_change();

-- =========================================================
-- Backfill existing threats with computed mitigation levels
-- =========================================================
UPDATE threat.threats t
SET mitigation_level = COALESCE(threat.compute_mitigation_level(t.id), 0)
WHERE mitigation_level IS NULL OR mitigation_level = 0;

COMMIT;

-- =========================================================
-- Verification queries (for testing)
-- =========================================================
/*
-- View computed mitigation levels vs threat_impact view
SELECT 
    t.id,
    t.tag,
    t.name,
    t.mitigation_level AS stored_mitigation_level,
    ROUND(ti.residual_risk_pct)::INTEGER AS computed_from_view,
    CASE 
        WHEN t.mitigation_level = ROUND(ti.residual_risk_pct)::INTEGER THEN '✓'
        ELSE '✗ MISMATCH'
    END AS status
FROM threat.threats t
LEFT JOIN threat.threat_impact ti 
    ON t.tag = ti.threat_tag AND ti.threat_tag != 'TOTAL'
ORDER BY t.id;

-- Test the function directly
SELECT threat.compute_mitigation_level(1) AS mitigation_for_threat_1;
*/
