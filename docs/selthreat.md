# selthreat: Canonical Threat Selector & Bulk Importer

## Overview

`selthreat` is a Python-based batch tool that intelligently selects the most plausible threats from the canonical basis set (model_id=35, containing 1,800 orthogonal threats) for FDA-cleared AI-enabled medical devices, then bulk-imports them into target threat models.

The tool uses **GPT-4o-mini** to semantically match device profiles against the canonical threat basis set, scoring each threat's relevance on a 1-10 scale, and selecting the top 8-12 threats for insertion.

## Use Case

This tool supports threat modeling workflows where:
1. You have a **canonical basis set** of pre-defined threats (model_id=35)
2. You need to **select relevant subsets** of those threats for specific devices
3. You want to **bulk-copy selected threats** to target models (e.g., placebo arm test models)
4. You want **reproducible, LLM-driven threat selection** based on device profiles

## Requirements

### Environment Variables (in `.env`)
```
DATABASE_URL=postgresql://user:password@localhost:5432/pattern-factory
OPENAI_API_KEY=sk-proj-...
```

### Database Access
- Read access to `public.products` (device profiles)
- Read access to `threat.threats` WHERE model_id=35 (canonical threats)
- Write access to `threat.threats` (target model, for selected threats)

## Installation

1. Ensure the service is installed:
   ```bash
   backend/services/threat_selector_service.py
   bin/selthreat (CLI wrapper)
   ```

2. Verify dependencies in `backend/requirements.txt`:
   ```
   asyncpg>=0.30.0
   openai>=1.0.0
   python-dotenv>=1.0.0
   ```

3. Make the script executable:
   ```bash
   chmod +x bin/selthreat
   ```

## Quick Start

### Preview Threats (No Database Changes)
```bash
./bin/selthreat list --device-id=5 --count=10
```

### Select and Import Threats
```bash
./bin/selthreat select --model-id=2 --device-id=5 --count=10
```

### Dry-Run Mode (Preview Only)
```bash
./bin/selthreat select --model-id=2 --device-id=5 --dry-run
```

### Batch Process Multiple Devices
```bash
./bin/selthreat select --model-id=2 --device-ids=5,12,18 --count=10
```

## Usage

### Commands

#### `select`
Select and bulk-import threats into a target model.

**Arguments:**
- `--model-id ID` *(required)* — Target threat model ID
- `--device-id ID` *(required, mutually exclusive with --device-ids)* — Single device/product ID
- `--device-ids IDS` *(required, mutually exclusive with --device-id)* — Comma-separated list of device IDs
- `--count N` *(optional, default 10)* — Number of threats to select (min 8, max 12)
- `--model MODEL` *(optional, default gpt-4o-mini)* — LLM model for threat selection
- `--dry-run` *(optional)* — Preview selections without writing to database
- `--verbose` *(optional)* — Enable debug-level logging

**Examples:**
```bash
# Select 10 threats for device 5, import to model 2
./bin/selthreat select --model-id=2 --device-id=5

# Select 8 threats for multiple devices
./bin/selthreat select --model-id=2 --device-ids=5,12,18 --count=8

# Preview selections before import
./bin/selthreat select --model-id=2 --device-id=5 --dry-run

# Verbose output for debugging
./bin/selthreat select --model-id=2 --device-id=5 --verbose
```

#### `list`
Preview selected threats without importing them.

**Arguments:**
- `--device-id ID` *(required)* — Device/product ID to preview
- `--count N` *(optional, default 10)* — Number of threats to preview (min 8, max 12)
- `--model MODEL` *(optional, default gpt-4o-mini)* — LLM model for threat selection
- `--verbose` *(optional)* — Enable debug-level logging

**Examples:**
```bash
# Preview 10 threats for device 5
./bin/selthreat list --device-id=5

# Preview 12 threats (maximum)
./bin/selthreat list --device-id=5 --count=12

# Verbose preview with LLM details
./bin/selthreat list --device-id=5 --verbose
```

## Output Format

### Successful Selection

```json
{
  "device_id": 5,
  "device_name": "Device Name",
  "target_model_id": 2,
  "threat_count_requested": 10,
  "threat_count_selected": 10,
  "threat_count_inserted": 10,
  "dry_run": false,
  "threats": [
    {
      "id": 575,
      "tag": "BASIS-1-004",
      "name": "Activity confounding",
      "domain": "clinical",
      "score": 9.2
    },
    {
      "id": 576,
      "tag": "BASIS-1-005",
      "name": "Adaptive planning error",
      "domain": "safety",
      "score": 8.7
    }
  ]
}
```

### List Preview Output

```json
{
  "device_id": 5,
  "device_name": "Device Name",
  "threat_count_requested": 10,
  "threat_count_selected": 10,
  "threats": [
    {
      "id": 575,
      "tag": "BASIS-1-004",
      "name": "Activity confounding",
      "description": "Voluntary daily activities...",
      "domain": "clinical",
      "score": 9.2
    }
  ]
}
```

## Threat Selection Algorithm

### Step 1: Load Canonical Basis Set
- Load all 1,800 threats from `threat.threats` WHERE `model_id=35`
- Store in memory as a Python list for fast access

### Step 2: Fetch Device Profile
Query `public.products` for:
- Device name
- Company
- Submission number
- Indicated use
- Device description
- Indications for use
- Panel (specialty)
- Primary product code

### Step 3: LLM Scoring
Send to GPT-4o-mini:
- Device profile text
- Full list of 1,800 canonical threats (JSON format)
- Task: "Rate each threat's plausibility for this device on a scale of 1-10"

**Scoring Priorities:**
- Clinical domain match (e.g., oncology, cardiology)
- AI/ML-specific risks (training data, model degradation, adversarial inputs)
- Integration risks (interfaces, data exchange)
- Patient safety impact scenarios
- Regulatory compliance risks

### Step 4: Select Top N Threats
- Sort scored threats by relevance score (descending)
- Select top N threats (default 10)
- Resolve full threat data from canonical set

### Step 5: Bulk Insert
Insert selected threats into target model via:
```sql
INSERT INTO threat.threats (
    model_id, tag, name, description, domain, probability,
    damage_description, spoofing, tampering, repudiation,
    information_disclosure, denial_of_service, elevation_of_privilege,
    mitigation_level, disabled, created_at, updated_at, card_id, version
)
VALUES (...)
ON CONFLICT (model_id, tag) DO NOTHING
```

Threats are copied **as-is** from the canonical set with only `model_id` changed.

## Testing & Validation

### Dry-Run Test (No Database Changes)
```bash
./bin/selthreat select --model-id=2 --device-id=254 --dry-run --verbose
```

This will:
1. Load the canonical threat basis set
2. Fetch device profile for device_id=254
3. Score all 1,800 threats against the device
4. Select top 10 threats
5. Print results to stdout
6. **NOT write to the database**

### Verify Threats Were Inserted
```bash
psql pattern-factory -c "
SELECT tag, name, domain, COUNT(*) 
FROM threat.threats 
WHERE model_id = 2 
  AND tag LIKE 'BASIS-1-%'
GROUP BY model_id, tag, name, domain
LIMIT 5;"
```

### Count Inserted Threats per Device
```bash
psql pattern-factory -c "
SELECT COUNT(*) as threat_count
FROM threat.threats
WHERE model_id = 2
  AND tag LIKE 'BASIS-1-%';"
```

## API (Python)

### Direct Service Usage

```python
from backend.services.threat_selector_service import ThreatSelectorService
import asyncio

async def example():
    service = ThreatSelectorService(
        db_url="postgresql://...",
        dry_run=False,
        llm_model="gpt-4o-mini"
    )
    
    await service.initialize()
    try:
        # Load canonical threats once
        await service.load_canonical_threats()
        
        # Select threats for a device
        result = await service.select_threats_for_device(
            target_model_id=2,
            device_id=5,
            threat_count=10
        )
        
        print(result)
    finally:
        await service.cleanup()

asyncio.run(example())
```

### Service Methods

#### `load_canonical_threats()`
Load all 1,800 canonical threats into memory.

#### `select_threats_for_device(target_model_id, device_id, threat_count)`
Select and insert threats for a device.

**Returns:** Dictionary with keys:
- `device_id`: Input device ID
- `device_name`: Device name from products table
- `target_model_id`: Target model ID
- `threat_count_requested`: Requested threat count
- `threat_count_selected`: Threats returned by LLM
- `threat_count_inserted`: Threats successfully inserted to DB
- `dry_run`: Whether dry-run mode was enabled
- `threats`: List of selected threats with scores

#### `list_selected_threats(device_id, threat_count)`
Preview threats without inserting them.

**Returns:** Same format as `select_threats_for_device`, but without `target_model_id` and `threat_count_inserted`.

#### `get_device_profile(device_id)`
Fetch device profile from products table.

**Returns:** Dictionary with device details.

## Configuration

### LLM Model Selection

Default: `gpt-4o-mini` (cost-effective, fast)

Supported models:
- `gpt-4o-mini` — Recommended for most use cases
- `gpt-4o` — Higher quality, higher cost
- `gpt-4-turbo` — Older, use gpt-4o instead

**Note:** The service hardcodes `temperature=0.2` for deterministic threat selection.

### Threat Count Constraints
- **Min:** 8 threats
- **Default:** 10 threats
- **Max:** 12 threats

Request values outside this range are clamped with a warning.

## Logging

Logs are printed to stdout with format:
```
YYYY-MM-DD HH:MM:SS [LEVEL] logger_name - message
```

### Log Levels
- `INFO` (default) — Progress, results, summary
- `DEBUG` (with --verbose) — Detailed operation tracking, LLM prompts

### Example Log Output
```
2026-08-18 18:47:22 [INFO] selthreat - Processing 1 device(s) with threat count 10
2026-08-18 18:47:22 [INFO] selthreat - [1/1] Selecting threats for device_id=5
2026-08-18 18:47:22 [INFO] threat_selector_service - Database pool initialized
2026-08-18 18:47:22 [INFO] threat_selector_service - Loaded 1800 canonical threats from model_id=35
2026-08-18 18:47:22 [INFO] threat_selector_service - Fetched device profile: Device Name (id=5)
2026-08-18 18:47:28 [INFO] threat_selector_service - LLM selected 10 threats for device 5
2026-08-18 18:47:28 [INFO] threat_selector_service - Resolved 10 threats from canonical set
2026-08-18 18:47:28 [INFO] threat_selector_service - Inserted threat BASIS-1-004 into model 2
...
2026-08-18 18:47:29 [INFO] selthreat - Summary: 1 device(s) processed, 10 threats selected, 10 threats inserted
```

## Performance

### Expected Timing
- **Load canonical threats:** 2-3 seconds (one-time)
- **Device processing:** 5-10 seconds per device
  - Device profile fetch: < 1s
  - LLM scoring: 5-8s
  - Database insert: 1-2s

### Memory Usage
- Canonical threats in memory: ~50-100 MB (1,800 threat objects)
- Single batch process: ~200 MB total

### Cost
- **Cost per device:** ~$0.001 - $0.005 (gpt-4o-mini)
- **Cost for 10 devices:** ~$0.01 - $0.05

## Troubleshooting

### Error: "Device (product) id X not found"
**Cause:** The device ID doesn't exist in `public.products`.
**Solution:** Verify the device ID with:
```bash
psql pattern-factory -c "SELECT id, device FROM public.products WHERE id = 5;"
```

### Error: "LLM threat selection failed"
**Cause:** OpenAI API error (rate limit, invalid key, timeout).
**Solution:**
1. Check `OPENAI_API_KEY` is set and valid
2. Check API rate limits: https://platform.openai.com/account/rate-limits
3. Retry with a shorter `--count` value

### Error: "Failed to parse LLM response"
**Cause:** LLM returned invalid JSON.
**Solution:**
1. Enable `--verbose` to see the raw LLM response
2. Retry (may be transient)
3. Use a different LLM model with `--model`

### Error: "Failed to insert threat X: UniqueViolationError"
**Cause:** Threat with same `(model_id, tag)` already exists.
**Solution:** Expected behavior. The tool uses `ON CONFLICT DO NOTHING` to skip duplicates. No action needed.

### Slow Processing
**Cause:** LLM timeout or slow network.
**Solution:**
1. Check internet connection
2. Reduce `--count` value (fewer threats to score)
3. Use a different LLM with `--model`

## Best Practices

### 1. Dry-Run First
Always test with `--dry-run` before bulk operations:
```bash
./bin/selthreat select --model-id=2 --device-id=5 --dry-run
```

### 2. Verify Device Profiles
Check that devices have complete profile data:
```bash
psql pattern-factory -c "
SELECT id, device, company, 
  CASE WHEN device_description IS NOT NULL THEN 'YES' ELSE 'NO' END as has_desc
FROM public.products 
WHERE id IN (5, 12, 18);"
```

### 3. Use Verbose Mode for Debugging
```bash
./bin/selthreat select --model-id=2 --device-id=5 --verbose
```

### 4. Process Devices Sequentially
For large batches, consider processing devices one at a time to allow monitoring:
```bash
./bin/selthreat select --model-id=2 --device-id=5
./bin/selthreat select --model-id=2 --device-id=12
./bin/selthreat select --model-id=2 --device-id=18
```

### 5. Verify Insertions
After import, verify threats were inserted:
```bash
psql pattern-factory -c "
SELECT COUNT(*) as threat_count
FROM threat.threats
WHERE model_id = 2 AND tag LIKE 'BASIS-1-%';"
```

## Future Enhancements

- **Threat caching:** Cache LLM-scored threat sets for re-use
- **Batch optimization:** Process multiple devices in parallel
- **Threat version tracking:** Store selection run metadata in database
- **Interactive mode:** Approve/reject individual threat selections
- **Similarity scoring:** Fuzzy-match to avoid duplicate selections
- **Integration with Warp agents:** Orchestrate selections via Oz platform

## See Also

- `backend/services/threat_selector_service.py` — Core service implementation
- `backend/services/basis_threats_service.py` — Related basis threat generation tool
- `threat.threats` table schema — Threat data model
- `public.products` table schema — Device profiles
