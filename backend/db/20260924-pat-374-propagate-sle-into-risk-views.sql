/*
 * PAT-374: propagate the quantitative threat model's SLE into the risk views.
 *
 * The project's quantitative threat model defines:
 *
 *   assets_at_risk       = sum(asset sle_value × damage %)          (gross_sle)
 *   sle                  = assets_at_risk × threat probability / 100
 *   sle_after_mitigation = sle × target residual multiplier (floored at 5%)
 *
 * The views computed and exposed the residual/mitigation steps but not the
 * probability-weighted SLE itself, so consumers could not read the model's
 * loss figure. This migration adds the SLE columns back, appending to the
 * existing views so current columns and consumers are unchanged:
 *
 *   sle, sle_after_mitigation on
 *     threat.threat_impact, public."THRIM", public."ENTERPRISE_RISK_TOP_5_SLE"
 *
 * The enterprise top-5 ranking is switched from gross exposure (gross_sle) to
 * the model's loss metric (sle).
 *
 * Run with psql:
 *
 *   psql pattern-factory \
 *     -f backend/db/20260924-pat-374-propagate-sle-into-risk-views.sql
 */

\set ON_ERROR_STOP on

BEGIN;

/*
 * 1. threat.threat_impact -- append sle and sle_after_mitigation.
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
        t.damage_description,
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
            (1.0 - COALESCE(tm.current_residual_multiplier, 1.0)) * 100,
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
            (1.0 - COALESCE(tm.target_residual_multiplier, 1.0)) * 100,
            1
        ) AS target_mitigation_pct,

        ROUND(
            COALESCE(tm.target_residual_multiplier, 1.0) * 100,
            1
        ) AS target_residual_exposure_pct,

        /* SLE = assets at risk × threat probability. */
        ROUND(
            SUM(
                COALESCE(a.sle_value, 0)
                * (at.damage / 100.0)
            )
            * COALESCE(t.probability, 0) / 100.0
        )::BIGINT AS sle,

        /* SLE after mitigation = SLE × residual multiplier (floored at 5%). */
        ROUND(
            SUM(
                COALESCE(a.sle_value, 0)
                * (at.damage / 100.0)
            )
            * COALESCE(t.probability, 0) / 100.0
            * COALESCE(tm.target_residual_multiplier, 1.0)
        )::BIGINT AS sle_after_mitigation

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
        t.damage_description,
        t.probability,
        tm.current_residual_multiplier,
        tm.target_residual_multiplier
)
SELECT
    threat_id,
    model_id,
    threat_tag,
    threat_name,
    damage_description,
    threat_probability,
    affected_asset_count,
    gross_sle,
    current_sle,
    current_mitigation_pct,
    current_residual_exposure_pct,
    target_sle,
    target_mitigation_pct,
    target_residual_exposure_pct,
    sle,
    sle_after_mitigation
FROM threat_details;


/*
 * 2. public."THRIM" -- append sle and sle_after_mitigation.
 */
CREATE OR REPLACE VIEW public."THRIM" AS
SELECT
    threat_tag,
    threat_name,
    damage_description,
    threat_probability,
    affected_asset_count,
    gross_sle,
    current_sle,
    target_sle,
    target_mitigation_pct,
    sle,
    sle_after_mitigation
FROM threat.threat_impact
WHERE threat_id IS NOT NULL;


/*
 * 3. public."ENTERPRISE_RISK_TOP_5_SLE" -- append sle and sle_after_mitigation
 *    and rank the top 5 by sle.
 */
CREATE OR REPLACE VIEW public."ENTERPRISE_RISK_TOP_5_SLE" AS
WITH threat_mitigation AS (
    SELECT
        ct.model_id,
        ct.threat_id,
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
        m.id AS model_id_link,
        m.name AS model_name,
        m.product_id,
        p.id AS product_id_link,
        p.device AS product_name,
        p.org_id,
        o.id AS org_id_link,
        o.name AS org_name,
        t.tag AS threat_tag,
        t.name AS threat_name,
        t.damage_description,
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
            (1.0 - COALESCE(tm.current_residual_multiplier, 1.0)) * 100,
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
            (1.0 - COALESCE(tm.target_residual_multiplier, 1.0)) * 100,
            1
        ) AS target_mitigation_pct,

        ROUND(
            COALESCE(tm.target_residual_multiplier, 1.0) * 100,
            1
        ) AS target_residual_exposure_pct,

        ROUND(
            SUM(
                COALESCE(a.sle_value, 0)
                * (at.damage / 100.0)
            )
            * COALESCE(t.probability, 0) / 100.0
        )::BIGINT AS sle,

        ROUND(
            SUM(
                COALESCE(a.sle_value, 0)
                * (at.damage / 100.0)
            )
            * COALESCE(t.probability, 0) / 100.0
            * COALESCE(tm.target_residual_multiplier, 1.0)
        )::BIGINT AS sle_after_mitigation

    FROM threat.threats t
    INNER JOIN threat.models m
        ON m.id = t.model_id
    LEFT JOIN public.products p
        ON p.id = m.product_id
    LEFT JOIN public.orgs o
        ON o.id = p.org_id
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
      AND o.id IS NOT NULL
    GROUP BY
        t.id,
        t.model_id,
        m.id,
        m.name,
        m.product_id,
        p.id,
        p.device,
        p.org_id,
        o.id,
        o.name,
        t.tag,
        t.name,
        t.damage_description,
        t.probability,
        tm.current_residual_multiplier,
        tm.target_residual_multiplier
),
ranked_threats AS (
    SELECT
        threat_id,
        model_id,
        model_id_link,
        model_name,
        product_id,
        product_id_link,
        product_name,
        org_id,
        org_id_link,
        org_name,
        threat_tag,
        threat_name,
        damage_description,
        threat_probability,
        affected_asset_count,
        gross_sle,
        current_sle,
        current_mitigation_pct,
        current_residual_exposure_pct,
        target_sle,
        target_mitigation_pct,
        target_residual_exposure_pct,
        sle,
        sle_after_mitigation,
        ROW_NUMBER() OVER (
            PARTITION BY org_id
            ORDER BY sle DESC
        ) AS rank_in_org
    FROM threat_details
)
SELECT
    threat_id,
    model_id,
    model_id_link,
    model_name,
    product_id,
    product_id_link,
    product_name,
    org_id,
    org_id_link,
    org_name,
    threat_tag,
    threat_name,
    damage_description,
    threat_probability,
    affected_asset_count,
    gross_sle,
    current_sle,
    current_mitigation_pct,
    current_residual_exposure_pct,
    target_sle,
    target_mitigation_pct,
    target_residual_exposure_pct,
    rank_in_org,
    sle,
    sle_after_mitigation
FROM ranked_threats
WHERE rank_in_org <= 5
ORDER BY org_id, rank_in_org;

COMMIT;
