-- =========================================================
-- Pattern Factory — Add countermeasures.yearly_cost to threat_impact view
-- Date: 2026-07-24
-- Purpose: Include total yearly mitigation cost per threat
--          in the threat.threat_impact view
-- =========================================================

BEGIN;

-- Drop dependent views first
DROP VIEW IF EXISTS "THRIM" CASCADE;
DROP VIEW IF EXISTS threat.threat_impact CASCADE;

-- Recreate threat_impact view with yearly_cost included
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
        END AS residual_risk_multiplier,
        -- Sum of yearly costs for all countermeasures mitigating this threat
        SUM(COALESCE(c.yearly_cost, 0)) AS total_yearly_cost
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
        END AS residual_risk_level,
        
        -- Total yearly cost of countermeasures for this threat
        COALESCE(tm.total_yearly_cost, 0)::INTEGER AS yearly_cost
    
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
    
    GROUP BY t.id, t.model_id, t.tag, t.name, t.probability, tm.residual_risk_multiplier, tm.total_yearly_cost 
    ORDER BY residual_risk_pct DESC
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
    END AS residual_risk_level,
    SUM(yearly_cost)::INTEGER AS yearly_cost
FROM threat_details;

-- Recreate public passthrough view with yearly_cost included
CREATE OR REPLACE VIEW "THRIM" AS
SELECT 
    threat_tag,
    threat_name,
    probability,
    mitigation_level,
    yearly_cost as "Cost of mitigation",
    var_before_mitigation,
    var_after_mitigation,
    residual_risk_pct,
    residual_risk_level
FROM threat.threat_impact;

COMMIT;
