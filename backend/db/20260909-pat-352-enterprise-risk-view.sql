/*
 * Enterprise Risk View - Top 5 Single Loss Exposure Events Per Organization
 *
 * This view aggregates threat impact data across all models and products
 * belonging to a given organization, ranking threats by gross_sle and
 * returning the top 5 threats per organization.
 *
 * Unlike threat.threat_impact which is model-specific (filtered by active_model),
 * this view provides organization-level SLE exposure across the entire product portfolio.
 */

DROP VIEW IF EXISTS "ENTERPRISE_RISK_TOP_5_SLE" CASCADE;

CREATE OR REPLACE VIEW "ENTERPRISE_RISK_TOP_5_SLE" AS
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
        m.id as model_id_link,
        m.name as model_name,
        m.product_id,
        p.id as product_id_link,
        p.device as product_name,
        p.org_id,
        o.id as org_id_link,
        o.name as org_name,
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
      AND o.id IS NOT NULL  -- Only include threats from org-owned products
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
        ROW_NUMBER() OVER (PARTITION BY org_id ORDER BY gross_sle DESC) as rank_in_org
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
    rank_in_org
FROM ranked_threats
WHERE rank_in_org <= 5
ORDER BY org_id, rank_in_org;
