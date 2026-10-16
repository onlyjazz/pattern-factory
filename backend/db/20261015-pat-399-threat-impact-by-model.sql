/*
 * PAT-399: expose threat impact for one model, keyed by product.
 *
 * threat.threat_impact is a logical view pinned to the single row in
 * public.active_models, so it can only ever report risk for whichever model
 * happens to be active, and it carries no product identity. This migration adds
 * the same computation for an explicit model, plus a product_id column resolved
 * through threat.models.product_id -- the same link
 * public."ENTERPRISE_RISK_TOP_5_SLE" uses.
 *
 * A set-returning function rather than a view because the model has to be a
 * parameter. A view can only read it from a table, which is exactly what pins
 * threat.threat_impact to active_models; the requirement here is always one
 * explicit model, never the whole model set.
 *
 *   SELECT * FROM threat.threat_impact(35);
 *
 * Scoping to the parameter also scopes the countermeasure rollup, so the
 * mitigation CTE aggregates one model's countermeasure_threat rows instead of
 * the whole table.
 *
 * The function coexists with the threat.threat_impact view: Postgres resolves
 * `FROM threat.threat_impact` to the relation and
 * `FROM threat.threat_impact(35)` to the function.
 *
 * Run with psql:
 *
 *   psql pattern-factory \
 *     -f backend/db/20261015-pat-399-threat-impact-by-model.sql
 */

\set ON_ERROR_STOP on

BEGIN;

/*
 * Column names, types and order match threat.threat_impact, with product_id
 * appended last.
 */
CREATE OR REPLACE FUNCTION threat.threat_impact(p_model_id integer)
RETURNS TABLE (
    threat_id integer,
    model_id integer,
    threat_tag text,
    threat_name varchar(255),
    damage_description text,
    threat_probability integer,
    affected_asset_count integer,
    gross_sle bigint,
    current_sle bigint,
    current_mitigation_pct numeric,
    current_residual_exposure_pct numeric,
    target_sle bigint,
    target_mitigation_pct numeric,
    target_residual_exposure_pct numeric,
    sle bigint,
    sle_after_mitigation bigint,
    product_id integer
)
LANGUAGE sql
STABLE
AS $$
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
      AND ct.model_id = p_model_id
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
        )::BIGINT AS sle_after_mitigation,

        /* Product behind the model this threat belongs to. */
        m.product_id

    FROM threat.threats t
    INNER JOIN threat.models m
        ON m.id = t.model_id
    INNER JOIN threat.asset_threat at
        ON at.threat_id = t.id
       AND at.model_id = t.model_id
    INNER JOIN threat.assets a
        ON a.id = at.asset_id
       AND a.model_id = at.model_id
    LEFT JOIN threat_mitigation tm
        ON tm.threat_id = t.id
       AND tm.model_id = t.model_id
    WHERE t.model_id = p_model_id
      AND t.disabled = false
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
        tm.target_residual_multiplier,
        m.product_id
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
    sle_after_mitigation,
    product_id
FROM threat_details;
$$;

COMMENT ON FUNCTION threat.threat_impact(integer) IS
    'Threat impact (gross/current/target SLE and mitigation) for one model, with product_id.';

COMMIT;
