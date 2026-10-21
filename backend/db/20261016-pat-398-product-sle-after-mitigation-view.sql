/*
 * PAT-398: product-level SLE after mitigation.
 *
 * Adds a logical (non-materialized) view that exposes the product and its
 * owning organization alongside the quantitative threat model's residual loss
 * figure:
 *
 *   public.product_sle_after_mitigation
 *     device, panel, superiority, name, size, sle_after_mitigation, product_id
 *
 * `product_id` is products.id, appended last so the view can still be
 * redefined with CREATE OR REPLACE (PostgreSQL only allows appending output
 * columns). It lets products join the view back to their own row.
 *
 * One row per product (products joined to orgs on products.org_id). The SLE
 * figure is the product's total exposure, i.e. the sum of the per-threat
 * sle_after_mitigation values of every model attached to the product.
 *
 * The arithmetic is taken verbatim from
 * backend/db/20260924-pat-374-propagate-sle-into-risk-views.sql so the numbers
 * reconcile with threat.threat_impact, public."THRIM" and
 * public."ENTERPRISE_RISK_TOP_5_SLE":
 *
 *   assets_at_risk       = sum(asset sle_value x damage %)
 *   sle                  = assets_at_risk x threat probability / 100
 *   sle_after_mitigation = sle x target residual multiplier (floored at 5%)
 *
 * The A1-A8 core-asset filter and the 5% residual floor match those views.
 *
 * Run with psql:
 *
 *   psql pattern-factory \
 *     -f backend/db/20261016-pat-398-product-sle-after-mitigation-view.sql
 */

\set ON_ERROR_STOP on

BEGIN;

CREATE OR REPLACE VIEW public.product_sle_after_mitigation AS
WITH threat_mitigation AS (
    -- Target residual multiplier per threat: 1 - combined countermeasure
    -- mitigation, floored at 5%.
    SELECT
        ct.model_id,
        ct.threat_id,
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
threat_sle AS (
    -- sle_after_mitigation = assets at risk x threat probability x residual
    -- multiplier, per threat.
    SELECT
        t.model_id,
        t.id AS threat_id,
        ROUND(
            SUM(
                COALESCE(a.sle_value, 0)
                * (at.damage / 100.0)
            )
            * COALESCE(t.probability, 0) / 100.0
            * COALESCE(tm.target_residual_multiplier, 1.0)
        )::BIGINT AS sle_after_mitigation
    FROM threat.threats t
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
        t.model_id,
        t.id,
        t.probability,
        tm.target_residual_multiplier
),
product_sle AS (
    -- Roll the threat-level figure up to the product, summing across the
    -- product's models.
    SELECT
        m.product_id,
        SUM(ts.sle_after_mitigation)::BIGINT AS sle_after_mitigation
    FROM threat.models m
    INNER JOIN threat_sle ts
        ON ts.model_id = m.id
    WHERE m.product_id IS NOT NULL
    GROUP BY m.product_id
)
SELECT
    p.device,
    p.panel,
    p.superiority,
    o.name,
    o.size,
    ps.sle_after_mitigation,
    p.id AS product_id
FROM products p
INNER JOIN orgs o
    ON o.id = p.org_id
LEFT JOIN product_sle ps
    ON ps.product_id = p.id
WHERE p.deleted_at IS NULL;

COMMIT;
