-- =========================================================
-- Pattern Factory — Rename risk_reduction to mitigation_level
-- Date: 2026-07-05
-- Purpose: Rename the threat.threat_impact and THRIM view column
--          "risk_reduction" to "mitigation_level" for consistency
--          with the threats.mitigation_level column and the
--          compute_mitigation_level function.
-- =========================================================

BEGIN;

-- Drop dependent passthrough view first
DROP VIEW IF EXISTS "THRIM" CASCADE;

-- Recreate base analytical view with renamed column
DROP VIEW IF EXISTS threat.threat_impact CASCADE;
CREATE OR REPLACE VIEW threat.threat_impact AS
WITH threat_mitigation AS (
    -- Calculate aggregate mitigation per threat from all countermeasures
    SELECT 
        ct.threat_id,
        -- Product of (1 - mitigation_level) for all countermeasures
        CASE 
            WHEN COUNT(ct.countermeasure_id) > 0 THEN
                EXP(SUM(LN(1 - ct.mitigation_level / 100.0)))
            ELSE 
                1.0  -- No countermeasures = no mitigation
        END AS residual_risk_multiplier
    FROM threat.countermeasure_threat ct
    INNER JOIN threat.countermeasures c 
        ON ct.countermeasure_id = c.id
    WHERE ct.included_in_mitigation = true
      AND c.implemented = true
      AND c.disabled = false
      AND ct.mitigation_level < 100  -- Avoid LN(0)
    GROUP BY ct.threat_id
),
threat_details AS (
    SELECT 
        t.model_id,
        t.tag AS threat_tag,
        t.name AS threat_name,
        t.probability,
        
        -- VaR before mitigation (as integer)
        ROUND(SUM(
            COALESCE(a.yearly_value, 0) * 
            (t.probability / 100.0) * 
            (at.damage / 100.0)
        ))::INTEGER AS var_before_mitigation,
        
        -- VaR after mitigation (as integer)
        ROUND(SUM(
            COALESCE(a.yearly_value, 0) * 
            (t.probability / 100.0) * 
            (at.damage / 100.0) * 
            COALESCE(tm.residual_risk_multiplier, 1.0)
        ))::INTEGER AS var_after_mitigation,
        
        -- Mitigation level as percentage formatted xx.x%
        -- (was "risk_reduction" — renamed for consistency with
        --  threats.mitigation_level and compute_mitigation_level)
        ROUND(
            (1 - COALESCE(tm.residual_risk_multiplier, 1.0)) * 100, 
            1
        )::TEXT || '%' AS mitigation_level,
        
        -- Residual risk percentage (numeric for calculation)
        ROUND(
            COALESCE(tm.residual_risk_multiplier, 1.0) * 100, 
            1
        ) AS residual_risk_pct,
        
        -- Qualitative risk level
        CASE 
            WHEN COALESCE(tm.residual_risk_multiplier, 1.0) * 100 <= 10 THEN 'Very Low'
            WHEN COALESCE(tm.residual_risk_multiplier, 1.0) * 100 <= 20 THEN 'Low'
            WHEN COALESCE(tm.residual_risk_multiplier, 1.0) * 100 <= 50 THEN 'Medium'
            ELSE 'High'
        END AS residual_risk_level
    
    FROM threat.threats t
    INNER JOIN threat.asset_threat at 
        ON t.id = at.threat_id AND t.model_id = at.model_id
    INNER JOIN threat.assets a 
        ON at.asset_id = a.id AND at.model_id = a.model_id
    LEFT JOIN threat_mitigation tm 
        ON t.id = tm.threat_id
    
    WHERE t.disabled = false 
      AND a.disabled = false
      AND t.model_id = (SELECT model_id FROM public.active_models LIMIT 1)
    
    GROUP BY t.id, t.model_id, t.tag, t.name, t.probability, tm.residual_risk_multiplier
)
-- Individual threats
SELECT * FROM threat_details

UNION ALL

-- Summary row
SELECT 
    (SELECT model_id FROM public.active_models LIMIT 1) AS model_id,
    'TOTAL' AS threat_tag,
    'Total Portfolio Risk' AS threat_name,
    NULL AS probability,
    SUM(var_before_mitigation) AS var_before_mitigation,
    SUM(var_after_mitigation) AS var_after_mitigation,
    ROUND(
        (1 - SUM(var_after_mitigation)::NUMERIC / NULLIF(SUM(var_before_mitigation), 0)) * 100,
        1
    )::TEXT || '%' AS mitigation_level,
    ROUND(
        SUM(var_after_mitigation)::NUMERIC / NULLIF(SUM(var_before_mitigation), 0) * 100,
        1
    ) AS residual_risk_pct,
    CASE 
        WHEN SUM(var_after_mitigation)::NUMERIC / NULLIF(SUM(var_before_mitigation), 0) * 100 <= 10 THEN 'Very Low'
        WHEN SUM(var_after_mitigation)::NUMERIC / NULLIF(SUM(var_before_mitigation), 0) * 100 <= 20 THEN 'Low'
        WHEN SUM(var_after_mitigation)::NUMERIC / NULLIF(SUM(var_before_mitigation), 0) * 100 <= 50 THEN 'Medium'
        ELSE 'High'
    END AS residual_risk_level
FROM threat_details;

-- Recreate public passthrough view (same columns as before minus model_id,
-- with mitigation_level replacing risk_reduction)
CREATE OR REPLACE VIEW "THRIM" AS
SELECT 
    threat_tag,
    threat_name,
    probability,
    var_before_mitigation,
    var_after_mitigation,
    mitigation_level,
    residual_risk_pct,
    residual_risk_level
FROM threat.threat_impact;

COMMIT;
