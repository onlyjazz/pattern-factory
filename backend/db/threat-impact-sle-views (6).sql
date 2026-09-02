/*
 * OpenCRO public-disclosure exposure views
 *
 * Financial exposure is modeled as Single Loss Expectancy (SLE):
 *
 *   asset SLE  = asset sle_value * asset_threat damage
 *   threat SLE = sum of affected-asset SLE
 *
 * Threat probability remains descriptive and is not used in the financial
 * calculation. Aggregate portfolio exposure is reported separately from
 * individual threat SLE.
 *
 * Countermeasures reduce remaining exposure multiplicatively. The public-data
 * model retains a minimum 5% residual exposure because public information
 * cannot support a claim that controls eliminate a credible threat completely.
 */

/*
 * SLE valuation basis
 *
 * sle_value is an explicit input to the public-disclosure model. It is not
 * derived by the legacy yearly-value trigger. Existing rows are backfilled once
 * so current models retain their values; new Cycle 5 assets should populate
 * sle_value directly from the asset taxonomy.
 */
ALTER TABLE threat.assets
    ADD COLUMN IF NOT EXISTS sle_value NUMERIC(15,2);

UPDATE threat.assets
SET sle_value = COALESCE(yearly_value, 0)
WHERE sle_value IS NULL;

ALTER TABLE threat.assets
    ALTER COLUMN sle_value SET DEFAULT 0,
    ALTER COLUMN sle_value SET NOT NULL;


DROP VIEW IF EXISTS "THRCM" CASCADE;
DROP VIEW IF EXISTS "THRIM" CASCADE;

DROP VIEW IF EXISTS threat.portfolio_exposure;
DROP VIEW IF EXISTS threat.asset_threat_exposure;
DROP VIEW IF EXISTS threat.asset_threat_exploitability;
DROP VIEW IF EXISTS threat.threat_countermeasures;
DROP VIEW IF EXISTS threat.threat_impact;


/*
 * One row per threat.
 *
 * Numeric values remain numeric. Formatting as currency or percentages belongs
 * in the reporting layer.
 */
CREATE OR REPLACE VIEW threat.threat_impact AS
WITH active_model AS (
    SELECT model_id
    FROM public.active_models
    LIMIT 1
),
threat_mitigation AS (
    SELECT
        ct.model_id,
        ct.threat_id,

        /*
         * Each mitigation level is applied to the remaining exposure.
         *
         * Individual values are clamped to 0..95 to avoid invalid inputs and
         * LN(0). Aggregate residual exposure is floored at 5%.
         */
        COALESCE(
            GREATEST(
                0.05,
                EXP(
                    SUM(
                        LN(
                            1.0
                            - LEAST(
                                GREATEST(
                                    COALESCE(ct.mitigation_level, 0),
                                    0
                                ),
                                95
                            ) / 100.0
                        )
                    ) FILTER (WHERE c.implemented = true)
                )
            ),
            1.0
        ) AS current_residual_multiplier,

        GREATEST(
            0.05,
            EXP(
                SUM(
                    LN(
                        1.0
                        - LEAST(
                            GREATEST(COALESCE(ct.mitigation_level, 0), 0),
                            95
                        ) / 100.0
                    )
                )
            )
        ) AS target_residual_multiplier

    FROM threat.countermeasure_threat ct
    INNER JOIN threat.countermeasures c
        ON c.id = ct.countermeasure_id
    WHERE ct.included_in_mitigation = true
      AND c.disabled = false
    GROUP BY ct.model_id, ct.threat_id
),
threat_details AS (
    SELECT
        t.id AS threat_id,
        t.model_id,
        t.tag AS threat_tag,
        t.name AS threat_name,

        /*
         * Probability is retained for context and prioritization, but does not
         * participate in SLE.
         */
        t.probability AS threat_probability,

        COUNT(DISTINCT at.asset_id)::INTEGER AS affected_asset_count,

        ROUND(
            SUM(
                COALESCE(a.sle_value, 0)
                * (at.damage / 100.0)
            )
        )::BIGINT AS gross_sle,

        ROUND(
            SUM(
                COALESCE(a.sle_value, 0)
                * (at.damage / 100.0)
                * COALESCE(tm.current_residual_multiplier, 1.0)
            )
        )::BIGINT AS current_sle,

        ROUND(
            (
                1.0
                - COALESCE(tm.current_residual_multiplier, 1.0)
            ) * 100,
            1
        ) AS current_mitigation_pct,

        ROUND(
            COALESCE(tm.current_residual_multiplier, 1.0) * 100,
            1
        ) AS current_residual_exposure_pct,

        ROUND(
            SUM(
                COALESCE(a.sle_value, 0)
                * (at.damage / 100.0)
                * COALESCE(tm.target_residual_multiplier, 1.0)
            )
        )::BIGINT AS target_sle,

        ROUND(
            (
                1.0
                - COALESCE(tm.target_residual_multiplier, 1.0)
            ) * 100,
            1
        ) AS target_mitigation_pct,

        ROUND(
            COALESCE(tm.target_residual_multiplier, 1.0) * 100,
            1
        ) AS target_residual_exposure_pct

    FROM threat.threats t
    INNER JOIN active_model am
        ON am.model_id = t.model_id
    INNER JOIN threat.asset_threat at
        ON at.threat_id = t.id
       AND at.model_id = t.model_id
    INNER JOIN threat.assets a
        ON a.id = at.asset_id
       AND a.model_id = at.model_id
    LEFT JOIN threat_mitigation tm
        ON tm.threat_id = t.id
       AND tm.model_id = t.model_id
    WHERE t.disabled = false
      AND a.disabled = false
      AND a.tag IN ('A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8')
    GROUP BY
        t.id,
        t.model_id,
        t.tag,
        t.name,
        t.probability,
        tm.current_residual_multiplier,
        tm.target_residual_multiplier
)
SELECT
    threat_id,
    model_id,
    threat_tag,
    threat_name,
    threat_probability,
    affected_asset_count,
    gross_sle,
    current_sle,
    current_mitigation_pct,
    current_residual_exposure_pct,
    target_sle,
    target_mitigation_pct,
    target_residual_exposure_pct
FROM threat_details;


/*
 * Aggregate exposure across all modeled threat scenarios.
 *
 * This is not the expected loss from one incident. It is the sum of the SLE
 * values for all modeled scenarios and should be described as aggregate modeled
 * portfolio exposure.
 */
CREATE OR REPLACE VIEW threat.portfolio_exposure AS
SELECT
    model_id,
    COUNT(*)::INTEGER AS threat_count,
    SUM(gross_sle)::BIGINT AS aggregate_gross_sle,
    SUM(current_sle)::BIGINT AS aggregate_current_sle,
    ROUND(
        (
            1.0
            - SUM(current_sle)::NUMERIC
              / NULLIF(SUM(gross_sle), 0)
        ) * 100,
        1
    ) AS current_portfolio_mitigation_pct,
    ROUND(
        SUM(current_sle)::NUMERIC
        / NULLIF(SUM(gross_sle), 0)
        * 100,
        1
    ) AS current_portfolio_residual_exposure_pct,
    SUM(target_sle)::BIGINT AS aggregate_target_sle,
    ROUND(
        (
            1.0
            - SUM(target_sle)::NUMERIC
              / NULLIF(SUM(gross_sle), 0)
        ) * 100,
        1
    ) AS target_portfolio_mitigation_pct,
    ROUND(
        SUM(target_sle)::NUMERIC
        / NULLIF(SUM(gross_sle), 0)
        * 100,
        1
    ) AS target_portfolio_residual_exposure_pct,
    MAX(gross_sle) AS largest_gross_sle,
    MAX(current_sle) AS largest_current_sle,
    MAX(target_sle) AS largest_target_sle
FROM threat.threat_impact
GROUP BY model_id;


/*
 * Asset-level components used to calculate each threat's SLE.
 */
CREATE OR REPLACE VIEW threat.asset_threat_exposure AS
WITH active_model AS (
    SELECT model_id
    FROM public.active_models
    LIMIT 1
)
SELECT
    a.model_id,
    a.id AS asset_id,
    a.name AS asset_name,
    t.id AS threat_id,
    t.tag AS threat_tag,
    t.name AS threat_name,
    t.probability AS threat_probability,
    COALESCE(a.sle_value, 0) AS asset_sle_value,
    at.damage AS threat_damage_to_asset,
    ROUND(
        COALESCE(a.sle_value, 0)
        * (at.damage / 100.0)
    )::BIGINT AS asset_sle
FROM threat.assets a
INNER JOIN active_model am
    ON am.model_id = a.model_id
INNER JOIN threat.asset_threat at
    ON at.asset_id = a.id
   AND at.model_id = a.model_id
INNER JOIN threat.threats t
    ON t.id = at.threat_id
   AND t.model_id = at.model_id
WHERE a.disabled = false
  AND t.disabled = false
  AND a.tag IN ('A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8');


/*
 * Countermeasure detail remains descriptive. Probability is numeric and
 * included_in_mitigation is exposed so downstream reports can distinguish the
 * modeled plan from other candidate countermeasures.
 */
CREATE OR REPLACE VIEW threat.threat_countermeasures AS
WITH active_model AS (
    SELECT model_id
    FROM public.active_models
    LIMIT 1
)
SELECT
    t.model_id,
    t.id AS threat_id,
    t.tag AS threat_tag,
    t.name AS threat_name,
    t.probability AS threat_probability,
    c.id AS countermeasure_id,
    c.tag AS countermeasure_tag,
    c.name AS countermeasure_name,
    ct.mitigation_level,
    ct.included_in_mitigation,
    c.implemented,
    c.disabled
FROM threat.threats t
INNER JOIN active_model am
    ON am.model_id = t.model_id
INNER JOIN threat.countermeasure_threat ct
    ON ct.threat_id = t.id
   AND ct.model_id = t.model_id
INNER JOIN threat.countermeasures c
    ON c.id = ct.countermeasure_id
WHERE t.disabled = false
ORDER BY t.tag, c.name;
