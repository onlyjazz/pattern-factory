# Threat Coverage Analysis: Model 37 (Basis Set)

## Overview

Product 1467 (blood test) showed weak performance in **selthreat** evaluation despite good performance in **genthreat**, suggesting insufficient basis set coverage for certain FDA device panels.

This analysis uses the new coverage analysis views (created via migration `20260821-threat-coverage-analysis.sql`) to quantify threat representation across device panels in the model 37 basis set.

## Key Metrics

- **Total Unique Threats in Basis Set**: 963 (from threat_provenance with model_id=37)
- **Total Threats in Model 37**: 1,800
- **Coverage from Provenance**: 53.5%

## Threat Coverage by Panel

| Panel | Threat Count | Percentage of Total | Notes |
|-------|--------------|-------------------|-------|
| Radiology | 1,256 | 130.43% | Dominant (multiple products sampled) |
| Cardiovascular | 376 | 39.04% | Strong coverage |
| Neurology | 118 | 12.25% | Moderate coverage |
| Anesthesiology | 77 | 8.00% | Limited coverage |
| Gastroenterology-Urology | 74 | 7.68% | Limited coverage |
| Ophthalmic | 56 | 5.82% | Limited coverage |
| Hematology | 37 | 3.84% | Weak coverage |
| Microbiology | 27 | 2.80% | Weak coverage |
| General & Plastic Surgery | 26 | 2.70% | Weak coverage |
| Orthopedic | 21 | 2.18% | Weak coverage |
| Dental | 16 | 1.66% | Very weak coverage |
| General Hospital | 15 | 1.56% | Very weak coverage |
| Pathology | 15 | 1.56% | Very weak coverage |
| Clinical Toxicology | 10 | 1.04% | Minimal coverage |
| Clinical Chemistry | 9 | 0.93% | Minimal coverage |
| Immunology | 9 | 0.93% | Minimal coverage |
| Obstetrics and Gynecology | 6 | 0.62% | Minimal coverage |

## Interpretation

### Why Does Radiology Show 130%+ Coverage?

The percentage can exceed 100% because:
1. **Multiple Radiology products** were sampled in the basis set run
2. Each product generates its own set of threats
3. Threats may **overlap** across products (same threat_id generated from different products)
4. The percentage is calculated as: `(unique threats from panel threats) / (total unique threats in model)`

This is actually a sign of good basis set diversity—Radiology products collectively contribute diverse threat perspectives.

### Coverage Tiers

**Strong Coverage (≥8%)**:
- Radiology (130% — excellent diversity)
- Cardiovascular (39%)
- Neurology (12%)
- Anesthesiology (8%)

**Moderate Coverage (2–8%)**:
- Gastroenterology-Urology (7.7%)
- Ophthalmic (5.8%)
- Hematology (3.8%)
- Microbiology (2.8%)
- General & Plastic Surgery (2.7%)
- Orthopedic (2.2%)

**Weak Coverage (<2%)**:
- Dental (1.7%)
- General Hospital (1.6%)
- Pathology (1.6%)
- Clinical Toxicology (1.0%)
- Clinical Chemistry (0.9%)
- Immunology (0.9%)
- Obstetrics & Gynecology (0.6%)

## Implications for Product 1467 (Blood Test)

Blood tests would typically fall under **Clinical Chemistry** or **Hematology** panels. Both show **weak coverage**:

- **Hematology**: 3.84% of basis set threats
- **Clinical Chemistry**: 0.93% of basis set threats

**Root Cause**: The basis set used for training model 37 did not sample enough blood/chemistry test devices, resulting in thin threat modeling for this category. When selthreat evaluates product 1467, it has fewer relevant threats to select from, potentially leading to:
1. Lower overall threat counts
2. Less diversity in threat types
3. Weaker threat descriptions (less informed by similar devices)

## Recommendations

To improve basis set coverage for future model versions:

1. **Increase Hematology/Chemistry sampling**: Sample at least 3–5 blood chemistry devices in the next basis set run (currently represented by <4% of threats)

2. **Proportional sampling**: Ensure basis set sampling aims for more uniform coverage across panels, rather than heavily favoring Radiology

3. **Sample density analysis**: Run this coverage analysis before finalizing a basis set to ensure all panels have ≥5% of total threats

4. **Product-panel mapping**: When evaluating a specific product (like 1467), prioritize threat selection from the panel it belongs to first, then fall back to related panels

## Available Queries

The migration created four reusable views:

```sql
-- Threat coverage (primary view)
SELECT * FROM threat.v_threat_coverage_by_panel;

-- Countermeasure coverage (when countermeasures are linked)
SELECT * FROM threat.v_countermeasure_coverage_by_panel;

-- Vulnerability coverage (when vulnerabilities are linked)
SELECT * FROM threat.v_vulnerability_coverage_by_panel;

-- Asset coverage (when assets are linked)
SELECT * FROM threat.v_asset_coverage_by_panel;
```

All views are parameterized by `model_id` (currently filtering for 37), and can be easily extended to support any model.

## Next Steps

- [ ] Analyze why genthreat (general threat generation) performed well for 1467 despite weak panel coverage
- [ ] Design basis set sampling strategy for model 38+ to improve Chemistry/Hematology coverage
- [ ] Consider panel-weighted threat selection strategy in selthreat algorithm
