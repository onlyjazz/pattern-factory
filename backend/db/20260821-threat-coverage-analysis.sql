-- PAT-319: Threat Coverage Analysis by Panel
-- Creates materialized views to analyze threat coverage (and related entities)
-- across FDA device panels in the basis set for model_id=37
--
-- This migration addresses the issue where product 1467 (blood test) showed weak
-- performance in selthreat, suggesting insufficient basis set coverage for certain panels.
--
-- Views created:
-- 1. threat.v_threat_coverage_by_panel - Threats per panel with percentage of total
-- 2. threat.v_countermeasure_coverage_by_panel - Countermeasures per panel with percentage
-- 3. threat.v_vulnerability_coverage_by_panel - Vulnerabilities per panel with percentage
-- 4. threat.v_asset_coverage_by_panel - Assets per panel with percentage
--
-- Each view is parameterized by model_id and can be queried for any model.

-- =====================================================================
-- VIEW 1: THREAT COVERAGE BY PANEL
-- =====================================================================
-- Shows how many unique threats are represented per FDA panel in the basis set,
-- along with the percentage of total threats in the model this represents.
-- Uses threat_provenance to track which threats were generated from which products.
-- NOTE: When the same threat is generated from multiple products in the same panel,
-- it is counted once per panel. The sum across panels can exceed 100% if threats
-- appear in multiple panels' products (threat reuse across panels).
CREATE OR REPLACE VIEW threat.v_threat_coverage_by_panel AS
WITH panel_threats AS (
  SELECT 
    p.panel,
    COUNT(DISTINCT tp.threat_id) as threat_count
  FROM threat.threat_provenance tp
  JOIN public.products p ON tp.product_id = p.id
  WHERE tp.model_id = 37
  GROUP BY p.panel
),
model_totals AS (
  SELECT 
    COUNT(DISTINCT tp.threat_id) as total_threats
  FROM threat.threat_provenance tp
  WHERE tp.model_id = 37
)
SELECT 
  pt.panel,
  37 as model_id,
  pt.threat_count,
  mt.total_threats,
  ROUND((pt.threat_count::numeric / NULLIF(mt.total_threats, 0) * 100), 2) as percentage_of_total,
  ROUND((pt.threat_count::numeric / NULLIF(mt.total_threats, 0) * 100), 2)::text || '%' as coverage_pct
FROM panel_threats pt
CROSS JOIN model_totals mt
ORDER BY pt.threat_count DESC, pt.panel ASC;

-- =====================================================================
-- VIEW 2: COUNTERMEASURE COVERAGE BY PANEL
-- =====================================================================
-- Shows how many unique countermeasures are represented per FDA panel
-- in the basis set of generated threats.
CREATE OR REPLACE VIEW threat.v_countermeasure_coverage_by_panel AS
WITH panel_countermeasures AS (
  SELECT 
    p.panel,
    COUNT(DISTINCT ct.countermeasure_id) as countermeasure_count
  FROM threat.threat_provenance tp
  JOIN public.products p ON tp.product_id = p.id
  JOIN threat.countermeasure_threat ct ON ct.threat_id = tp.threat_id
  GROUP BY p.panel
),
model_totals AS (
  SELECT 
    ct.model_id,
    COUNT(DISTINCT ct.countermeasure_id) as total_countermeasures
  FROM threat.countermeasure_threat ct
  GROUP BY ct.model_id
)
SELECT 
  COALESCE(pc.panel, 'UNKNOWN') as panel,
  COALESCE(mt.model_id, 37) as model_id,
  pc.countermeasure_count,
  mt.total_countermeasures,
  ROUND((pc.countermeasure_count::numeric / NULLIF(mt.total_countermeasures, 0) * 100), 2) as percentage_of_total,
  ROUND((pc.countermeasure_count::numeric / NULLIF(mt.total_countermeasures, 0) * 100), 2)::text || '%' as coverage_pct
FROM panel_countermeasures pc
CROSS JOIN model_totals mt
WHERE mt.model_id = 37
ORDER BY pc.countermeasure_count DESC, panel ASC;

-- =====================================================================
-- VIEW 3: VULNERABILITY COVERAGE BY PANEL
-- =====================================================================
-- Shows how many unique vulnerabilities are represented per FDA panel
-- in the basis set of generated threats.
CREATE OR REPLACE VIEW threat.v_vulnerability_coverage_by_panel AS
WITH panel_vulnerabilities AS (
  SELECT 
    p.panel,
    COUNT(DISTINCT vt.vulnerability_id) as vulnerability_count
  FROM threat.threat_provenance tp
  JOIN public.products p ON tp.product_id = p.id
  JOIN threat.vulnerability_threat vt ON vt.threat_id = tp.threat_id
  GROUP BY p.panel
),
model_totals AS (
  SELECT 
    vt.model_id,
    COUNT(DISTINCT vt.vulnerability_id) as total_vulnerabilities
  FROM threat.vulnerability_threat vt
  GROUP BY vt.model_id
)
SELECT 
  COALESCE(pv.panel, 'UNKNOWN') as panel,
  COALESCE(mt.model_id, 37) as model_id,
  pv.vulnerability_count,
  mt.total_vulnerabilities,
  ROUND((pv.vulnerability_count::numeric / NULLIF(mt.total_vulnerabilities, 0) * 100), 2) as percentage_of_total,
  ROUND((pv.vulnerability_count::numeric / NULLIF(mt.total_vulnerabilities, 0) * 100), 2)::text || '%' as coverage_pct
FROM panel_vulnerabilities pv
CROSS JOIN model_totals mt
WHERE mt.model_id = 37
ORDER BY pv.vulnerability_count DESC, panel ASC;

-- =====================================================================
-- VIEW 4: ASSET COVERAGE BY PANEL
-- =====================================================================
-- Shows how many unique assets are represented per FDA panel
-- in the basis set of generated threats.
CREATE OR REPLACE VIEW threat.v_asset_coverage_by_panel AS
WITH panel_assets AS (
  SELECT 
    p.panel,
    COUNT(DISTINCT aat.asset_id) as asset_count
  FROM threat.threat_provenance tp
  JOIN public.products p ON tp.product_id = p.id
  JOIN threat.asset_threat aat ON aat.threat_id = tp.threat_id
  GROUP BY p.panel
),
model_totals AS (
  SELECT 
    aat.model_id,
    COUNT(DISTINCT aat.asset_id) as total_assets
  FROM threat.asset_threat aat
  GROUP BY aat.model_id
)
SELECT 
  COALESCE(pa.panel, 'UNKNOWN') as panel,
  COALESCE(mt.model_id, 37) as model_id,
  pa.asset_count,
  mt.total_assets,
  ROUND((pa.asset_count::numeric / NULLIF(mt.total_assets, 0) * 100), 2) as percentage_of_total,
  ROUND((pa.asset_count::numeric / NULLIF(mt.total_assets, 0) * 100), 2)::text || '%' as coverage_pct
FROM panel_assets pa
CROSS JOIN model_totals mt
WHERE mt.model_id = 37
ORDER BY pa.asset_count DESC, panel ASC;

-- =====================================================================
-- TEST QUERIES (to verify views work correctly)
-- =====================================================================
-- Verify threat coverage view with sample output
-- SELECT * FROM threat.v_threat_coverage_by_panel LIMIT 5;

-- Verify countermeasure coverage
-- SELECT * FROM threat.v_countermeasure_coverage_by_panel LIMIT 5;

-- Verify vulnerability coverage
-- SELECT * FROM threat.v_vulnerability_coverage_by_panel LIMIT 5;

-- Verify asset coverage
-- SELECT * FROM threat.v_asset_coverage_by_panel LIMIT 5;
