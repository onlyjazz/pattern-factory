# selthreat: Canonical Threat Selection Tool

## Overview

`selthreat` is a Python-based tool that intelligently selects the most plausible threats from a canonical basis set (1,800 orthogonal threats, model_id=35) for FDA-cleared AI-enabled medical devices, then bulk-imports them into target threat models.

The tool uses a **three-stage semantic filtering pipeline** to eliminate hallucination and ensure clinically relevant threat selection.

## Development Summary

### Initial Approach (Failed)
- **Problem**: Direct LLM scoring of 1,800 threats caused hallucination
- **Outcome**: Selected threats from unrelated domains (LVEF cardiac screening for bone density device)
- **Root cause**: LLM overwhelmed by massive threat list without descriptions

### Iteration 1: Optimized Prompts & Two-Pass Validation
- **Implementation**: Compact threat summaries (name/domain only) + separate validation pass
- **Result**: Reduced hallucination but still selected some irrelevant threats
- **Issue**: Without threat descriptions, scoring was still unreliable

### Iteration 2: Panel-Based Filtering
- **Implementation**: Use `threat_provenance` table to filter threats by product panel
- **Result**: Radiology panel reduced 1,800 → 1,256 threats
- **Problem**: Panel still too broad (radiography + ultrasound + MRI, etc.)

### Final Solution: Three-Stage Semantic Filtering Pipeline ✅

## Architecture

### Three-Stage Pipeline

```
1. PANEL FILTERING
   1,800 canonical threats → filter by device.panel → ~1,200 candidate threats
   (Uses threat_provenance table)

2. SEMANTIC FILTERING  
   ~1,200 candidate threats → match descriptions to device profile → ~100-150 relevant threats
   (Uses LLM to match threat.description + threat.damage_description 
    vs. product.indicated_use + product.device_description + product.indications_for_use)

3. SCORING & SELECTION
   ~100-150 relevant threats → score by LLM → select top 8-12 → insert into target model
```

### Key Components

**File**: `backend/services/threat_selector_service.py`
- `load_canonical_threats(panel=None)` — Load threats with optional panel filtering
- `_filter_threats_by_device_profile()` — Semantic filtering using LLM
- `select_threats_for_device()` — Main orchestration method
- `_validate_threats_with_descriptions()` — Two-pass validation for borderline threats

**File**: `bin/selthreat`
- CLI with `select` and `list` subcommands
- `--model` parameter supports `gpt-4o-mini` (default) and `gpt-5.6-terra` (recommended)
- `--count` parameter (8-12 threats, default 10)
- `--dry-run` mode for previewing

**Configuration**: `prompts/rules/BASIS_THREATS.yaml`
- `SELTHREAT` key documents threat selection approach
- Initial and validation scoring prompts
- Classification basis (intended_use, indications_for_use, device_description)
- Threat matching criteria (name, description, domain, STRIDE flags)

## How It Works

### Stage 1: Panel Filtering
Query threats with provenance from same panel as device:
```sql
SELECT DISTINCT t.* 
FROM threat.threats t
INNER JOIN threat.threat_provenance tp ON t.id = tp.threat_id
INNER JOIN public.products p ON tp.product_id = p.id
WHERE t.model_id = 35 AND p.panel = ?
```

### Stage 2: Semantic Filtering
LLM reads threat descriptions and device profile, determines relevance:
- Input: threat description + damage_description + device intended_use + device_description
- Output: JSON array of threat IDs to keep
- Logic: "Does this threat apply to this device's specific function?"

### Stage 3: Scoring & Selection
LLM scores remaining threats by plausibility:
- Input: threat names/domains + device profile
- Output: JSON array of {id, score} pairs
- Selection: Top N threats by score

## Model Support

### gpt-4o-mini (Default)
- **Pros**: Cost-effective, reliable, good for deterministic tasks
- **Temperature**: 0.2 (initial scoring), 0.0-0.1 (validation/filtering)
- **Use case**: Testing, development

### gpt-5.6-terra (Recommended)
- **Pros**: Larger context window, superior semantic understanding
- **Temperature**: 1.0 (fixed, no parameter control)
- **Cons**: Higher cost
- **Use case**: Production, large device sets

## Testing Results

### Example: Rho (Bone Density Radiography Screening)
Device specs:
- Intended use: Analyzes frontal radiographs (lumbar, thoracic, chest, pelvis, knee, hand) to estimate bone mineral density
- Panel: Radiology
- Target population: 50+ years old

**Selection results** (with three-stage pipeline + gpt-5.6-terra):
1. BMD estimation error
2. Threshold misclassification
3. Out-of-distribution image performance
4. AI performance drift
5. Distribution shift
6. Unsupported population or image performance
7. Model performance degradation
8. Wrong patient association
9. Image-result mismatch
10. Diagnostic overreliance

**Filtering stats**:
- Panel filtering: 1,800 → 1,256 threats
- Semantic filtering: 1,256 → 131 threats (10% retained)
- Final selection: 10 threats inserted

All threats are clinically coherent and device-specific. No hallucinations (no ultrasound, cardiac, breast, spinal, or prostate threats).

## CLI Usage

### Select Threats (with import)
```bash
./bin/selthreat select --model-id=36 --device-id=599 --count=10 --model=gpt-5.6-terra
```

### Preview Threats (no import)
```bash
./bin/selthreat list --device-id=599 --count=10 --model=gpt-5.6-terra
```

### Dry-Run Mode
```bash
./bin/selthreat select --model-id=36 --device-id=599 --dry-run
```

## Configuration in BASIS_THREATS.yaml

The `SELTHREAT` section documents:
- **Classification basis**: Threat selection is based on device intended_use, indications_for_use, device_description
- **Threat matching criteria**: Uses threat name, description, domain, and STRIDE flags
- **Initial scoring prompt**: Rate threats 1-10 by plausibility to device profile
- **Validation scoring prompt**: Determine if threats apply to deployed device at runtime

## Key Insights

1. **Panel alone is insufficient** — Radiography includes radiography, ultrasound, MRI, CT. Need semantic filtering.

2. **Threat descriptions are essential** — LLM must read full threat description + damage_description to evaluate relevance.

3. **Device profile specificity matters** — Match against:
   - Intended use (clinical purpose)
   - Device description (technical details, modality)
   - Indications for use (what the device treats/screens)

4. **gpt-5.6-terra excels at semantic matching** — Larger context window allows comprehensive threat filtering in one pass.

5. **Provenance is gold** — The `threat_provenance` table, combined with panel matching, provides excellent grounding for semantic filtering.

## Future Enhancements

- Caching of semantic filter results per device profile
- Batch processing optimization for multiple devices
- Threat versioning and update tracking
- Integration with threat monitoring dashboards
- Performance metrics and audit logging

## Files Changed

- **Created**: `backend/services/threat_selector_service.py` (570+ lines)
- **Created**: `bin/selthreat` (280+ lines CLI wrapper)
- **Updated**: `prompts/rules/BASIS_THREATS.yaml` (added SELTHREAT section)
- **Created**: `docs/selthreat.md` (comprehensive user documentation)

## Testing Status

✅ Unit testing: Threat loading, panel filtering, semantic filtering, LLM calls
✅ Integration testing: End-to-end selection for Rho (Radiology, bone density)
✅ Edge cases: Panel mismatches, empty threat sets, LLM failures

**Ready for production testing on additional devices and panels tomorrow.**
