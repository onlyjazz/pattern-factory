# Threat Coverage Analysis Queries

These queries demonstrate how to use the four new coverage analysis views created in migration `20260821-threat-coverage-analysis.sql`.

## 1. Primary: Threat Coverage by Panel

Shows how many unique threats are generated from each FDA device panel in the basis set.

```sql
-- View all panels with threat coverage
SELECT * FROM threat.v_threat_coverage_by_panel;

-- Find weak coverage panels (less than 5% of total threats)
SELECT panel, threat_count, coverage_pct
FROM threat.v_threat_coverage_by_panel
WHERE percentage_of_total < 5
ORDER BY threat_count ASC;

-- Find panels with strong coverage (more than 10% of total threats)
SELECT panel, threat_count, percentage_of_total
FROM threat.v_threat_coverage_by_panel
WHERE percentage_of_total > 10
ORDER BY threat_count DESC;
```

### Sample Output (Model 37)

```
            panel            | threat_count | percentage_of_total
-----------------------------+--------------+---------------------
 Radiology                   |         1256 |              130.43
 Cardiovascular              |          376 |               39.04
 Neurology                   |          118 |               12.25
 Anesthesiology              |           77 |                8.00
 ... (13 more panels with lower coverage)
```

## 2. Countermeasure Coverage by Panel

Shows how many unique countermeasures are represented per panel (when countermeasure-threat links are populated).

```sql
-- View all panels with countermeasure coverage
SELECT * FROM threat.v_countermeasure_coverage_by_panel;

-- Show only panels with at least 10 countermeasures
SELECT panel, countermeasure_count, coverage_pct
FROM threat.v_countermeasure_coverage_by_panel
WHERE countermeasure_count >= 10
ORDER BY countermeasure_count DESC;
```

## 3. Vulnerability Coverage by Panel

Shows how many unique vulnerabilities are represented per panel (when vulnerability-threat links are populated).

```sql
-- View all panels with vulnerability coverage
SELECT * FROM threat.v_vulnerability_coverage_by_panel;

-- Find panels with no vulnerability coverage
SELECT panel
FROM threat.v_vulnerability_coverage_by_panel
WHERE vulnerability_count = 0;
```

## 4. Asset Coverage by Panel

Shows how many unique assets are represented per panel (when asset-threat links are populated).

```sql
-- View all panels with asset coverage
SELECT * FROM threat.v_asset_coverage_by_panel;

-- Compare asset coverage across panels
SELECT panel, asset_count, 
       ROUND(percentage_of_total, 1) as pct
FROM threat.v_asset_coverage_by_panel
ORDER BY asset_count DESC;
```

## Analysis Patterns

### Finding Coverage Gaps

```sql
-- Identify all four coverage metrics for panels with weak threat coverage
WITH weak_panels AS (
  SELECT panel 
  FROM threat.v_threat_coverage_by_panel 
  WHERE percentage_of_total < 5
)
SELECT 
  tc.panel,
  tc.threat_count as threats,
  COALESCE(cc.countermeasure_count, 0) as countermeasures,
  COALESCE(vc.vulnerability_count, 0) as vulnerabilities,
  COALESCE(ac.asset_count, 0) as assets
FROM weak_panels wp
JOIN threat.v_threat_coverage_by_panel tc ON tc.panel = wp.panel
LEFT JOIN threat.v_countermeasure_coverage_by_panel cc ON cc.panel = wp.panel
LEFT JOIN threat.v_vulnerability_coverage_by_panel vc ON vc.panel = wp.panel
LEFT JOIN threat.v_asset_coverage_by_panel ac ON ac.panel = wp.panel
ORDER BY tc.threat_count DESC;
```

### Coverage Distribution Summary

```sql
-- Summarize coverage distribution across all panels
SELECT 
  COUNT(*) as total_panels,
  ROUND(AVG(threat_count), 2) as avg_threats_per_panel,
  MIN(threat_count) as min_threats,
  MAX(threat_count) as max_threats,
  STDDEV(threat_count) as stddev_threats
FROM threat.v_threat_coverage_by_panel;

-- Output:
-- total_panels | avg_threats_per_panel | min_threats | max_threats | stddev_threats
-- --------------|----------------------|-------------|-------------|---------------
--           17 |               56.65  |           6 |        1256 |        290.89
```

### Panel Coverage Clustering

```sql
-- Classify panels by coverage tier
SELECT 
  panel,
  threat_count,
  CASE 
    WHEN percentage_of_total >= 30 THEN 'Excellent (≥30%)'
    WHEN percentage_of_total >= 10 THEN 'Good (10-30%)'
    WHEN percentage_of_total >= 5 THEN 'Moderate (5-10%)'
    WHEN percentage_of_total >= 2 THEN 'Weak (2-5%)'
    ELSE 'Minimal (<2%)'
  END as coverage_tier
FROM threat.v_threat_coverage_by_panel
ORDER BY 
  CASE 
    WHEN percentage_of_total >= 30 THEN 1
    WHEN percentage_of_total >= 10 THEN 2
    WHEN percentage_of_total >= 5 THEN 3
    WHEN percentage_of_total >= 2 THEN 4
    ELSE 5
  END,
  threat_count DESC;
```

### Basis Set Sampling Recommendation

```sql
-- Identify panels needing more representation (< 5% of total threats)
SELECT 
  panel,
  threat_count,
  ROUND(percentage_of_total, 1) as coverage_pct,
  'NEED MORE' as recommendation
FROM threat.v_threat_coverage_by_panel
WHERE percentage_of_total < 5
ORDER BY threat_count ASC;

-- Output can guide next basis set sampling:
-- Panels with <5% coverage should have 3-5 devices sampled
-- Panels with 5-10% coverage should have 2-3 devices sampled
-- Panels with >10% coverage can maintain current sampling
```

## Extending the Views

To extend analysis to other models or create material views:

### Create a Materialized View (for performance)

```sql
CREATE MATERIALIZED VIEW threat.mv_threat_coverage_by_panel_model37 AS
SELECT * FROM threat.v_threat_coverage_by_panel
WHERE model_id = 37;

-- Create index for fast queries
CREATE INDEX idx_threat_coverage_panel 
  ON threat.mv_threat_coverage_by_panel_model37(panel);

-- Refresh periodically:
REFRESH MATERIALIZED VIEW threat.mv_threat_coverage_by_panel_model37;
```

### Multi-Model Comparison

```sql
-- Compare threat coverage across multiple models (requires models to exist)
SELECT 
  tc37.panel,
  tc37.threat_count as model37_threats,
  tc38.threat_count as model38_threats,
  CASE 
    WHEN tc37.threat_count > tc38.threat_count THEN 'Better'
    WHEN tc37.threat_count < tc38.threat_count THEN 'Worse'
    ELSE 'Equal'
  END as trend
FROM threat.v_threat_coverage_by_panel tc37
FULL OUTER JOIN threat.v_threat_coverage_by_panel tc38 
  ON tc37.panel = tc38.panel 
  AND tc38.model_id = 38
WHERE tc37.model_id = 37
ORDER BY tc37.threat_count DESC;
```

## Migration Details

**File**: `/Users/dl/code/pattern-factory/backend/db/20260821-threat-coverage-analysis.sql`

**Views Created**:
1. `threat.v_threat_coverage_by_panel` — Primary view for threat analysis
2. `threat.v_countermeasure_coverage_by_panel` — For countermeasure diversity
3. `threat.v_vulnerability_coverage_by_panel` — For vulnerability diversity
4. `threat.v_asset_coverage_by_panel` — For asset diversity

**Dependencies**:
- `threat.threat_provenance` — Tracks which threats came from which products
- `threat.threats` — The actual threat entities
- `public.products` — FDA device metadata with panel field
- Optional: `threat.countermeasure_threat`, `threat.vulnerability_threat`, `threat.asset_threat` — For extended views

All views filter on `model_id = 37` by default, but can be easily modified for other models.
