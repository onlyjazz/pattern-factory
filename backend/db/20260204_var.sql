DROP VIEW threat.threat_impact;
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
        
        -- Risk reduction as percentage formatted xx.x%
        ROUND(
            (1 - COALESCE(tm.residual_risk_multiplier, 1.0)) * 100, 
            1
        )::TEXT || '%' AS risk_reduction,
        
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
    
    GROUP BY t.id, t.tag, t.name, t.probability, tm.residual_risk_multiplier
)
-- Individual threats
SELECT * FROM threat_details

UNION ALL

-- Summary row
SELECT 
    'TOTAL' AS threat_tag,
    'Total Portfolio Risk' AS threat_name,
    NULL AS probability,
    SUM(var_before_mitigation) AS var_before_mitigation,
    SUM(var_after_mitigation) AS var_after_mitigation,
    ROUND(
        (1 - SUM(var_after_mitigation)::NUMERIC / NULLIF(SUM(var_before_mitigation), 0)) * 100,
        1
    )::TEXT || '%' AS risk_reduction,
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

/*
Now your output will look like:

threat_tag | threat_name              | probability | var_before | var_after | risk_reduction | residual_risk_pct | residual_risk_level
-----------|--------------------------|-------------|-----------|-----------|----------------|-------------------|--------------------
R1         | Change Preset Config     | 40          | 384000    | 76800     | 80.0%          | 20.0              | Low
R2         | Supply chain attack      | 20          | 740000    | 370       | 100.0%         | 0.1               | Very Low
R3         | Remove System Plug       | 30          | 288000    | 1440      | 99.5%          | 0.5               | Very Low
R4         | Field Service Rep...     | 20          | 672000    | 7         | 100.0%         | 0.0               | Very Low
R5         | Sabotage                 | 10          | 420000    | 4200      | 99.0%          | 1.0               | Very Low
R6         | Change Sensor Parameters | 20          | 384000    | 38        | 100.0%         | 0.0               | Very Low
R7         | Software Hack or Attack  | 20          | 672000    | 672       | 99.9%          | 0.1               | Very Low
TOTAL      | Total Portfolio Risk     |             | 3560000   | 83527     | 97.7%          | 2.3               | Very Low
*/
--
--
DROP VIEW IF EXISTS threat.threat_countermeasures;
CREATE OR REPLACE VIEW threat.threat_countermeasures AS
SELECT 
    CASE 
        WHEN ROW_NUMBER() OVER (PARTITION BY t.tag ORDER BY c.name) = 1 
        THEN t.tag 
        ELSE '' 
    END AS threat_tag,
    CASE 
        WHEN ROW_NUMBER() OVER (PARTITION BY t.tag ORDER BY c.name) = 1 
        THEN t.name 
        ELSE '' 
    END AS threat_name,
    CASE 
        WHEN ROW_NUMBER() OVER (PARTITION BY t.tag ORDER BY c.name) = 1 
        THEN t.probability::TEXT 
        ELSE '' 
    END AS probability,
    c.tag AS countermeasure_tag,
    c.name AS countermeasure_name,
    ct.mitigation_level,
    c.implemented,
    c.disabled
FROM threat.threats t
INNER JOIN threat.countermeasure_threat ct 
    ON t.id = ct.threat_id AND t.model_id = ct.model_id
INNER JOIN threat.countermeasures c 
    ON ct.countermeasure_id = c.id AND ct.model_id = c.model_id
WHERE t.disabled = false
  AND ct.included_in_mitigation = true
ORDER BY t.tag, c.name;