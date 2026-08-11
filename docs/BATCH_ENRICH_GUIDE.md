# Batch Organization Enrichment Guide

Batch enrich organization records (funding, revenue, employee count, headquarters) using the ENRICH agent workflow.

## Quick Start

```bash
cd /Users/dl/code/pattern-factory

# Enrich organizations with id between 1 and 50
python backend/scripts/batch_enrich_orgs.py --id-range 1 50

# Enrich organizations 1-100 with CSV export
python backend/scripts/batch_enrich_orgs.py --id-range 1 100 --output results.csv

# Enrich with custom confidence threshold (auto-approve >= 0.80)
python backend/scripts/batch_enrich_orgs.py --id-range 1 50 --confidence 0.80

# Enrich large batch (e.g., all missing records)
python backend/scripts/batch_enrich_orgs.py --id-range 1 807 --output full_results.csv
```

## Prerequisites

### Environment Variables

Required for the ENRICH workflow:

```bash
# PostgreSQL connection (pick one approach)
# Option A: Full DATABASE_URL
export DATABASE_URL="postgresql://pattern_factory:314159@localhost:5432/pattern-factory"

# Option B: Individual PG variables (default values below)
export PGHOST=127.0.0.1
export PGPORT=5432
export PGUSER=pattern_factory
export PGPASSWORD=314159
export PGDATABASE=pattern-factory

# API keys (required for enrichment)
export OPENAI_API_KEY="sk-..."
export EXA_API_KEY="..."
```

## Command Reference

### Basic Usage

```bash
python backend/scripts/batch_enrich_orgs.py --id-range MIN MAX [options]
```

### Arguments

**`--id-range MIN MAX`** (required)
- Enrich organizations where `id BETWEEN MIN AND MAX` (inclusive)
- Examples:
  - `--id-range 1 50` → enrich orgs 1-50
  - `--id-range 100 200` → enrich orgs 100-200
  - `--id-range 1 807` → enrich all orgs (assuming max ID is 807)

**`--confidence THRESHOLD`** (optional, default: 0.70)
- Auto-approve and write to database if extraction confidence >= threshold
- Ranges: 0.0 to 1.0
- Examples:
  - `--confidence 0.70` → conservative (only high-confidence extractions)
  - `--confidence 0.60` → less conservative (more auto-approvals, may include lower-quality data)
  - `--confidence 0.90` → very conservative (most go to manual review)

**`--output PATH`** (optional)
- Export results to CSV file
- Useful for analysis and tracking
- Examples:
  - `--output results.csv`
  - `--output /tmp/batch-results-$(date +%Y%m%d).csv`

## Examples

### Example 1: Quick Test (10 orgs)
```bash
python backend/scripts/batch_enrich_orgs.py --id-range 1 10
```

Output:
```
2026-08-11 10:30:45,123 | INFO     | ✅ Connected to PostgreSQL
2026-08-11 10:30:45,234 | INFO     | 📦 Fetched 8 orgs to enrich (id between 1 and 10)

================================================================================
Starting batch enrichment for 8 organizations
ID Range: [1, 10]
Confidence threshold: 0.70
================================================================================

[1/8] Processing org ID 1: Apple Inc
  [1/4] Validating org name: Apple Inc
         Decision: yes (confidence: 0.99)
  [2/4] Searching for enrichment data...
         Decision: yes (confidence: 0.90)
  [3/4] Verifying extraction results with LLM...
         Decision: yes (confidence: 0.85)
  [4/4] Auto-approving and writing to database (confidence: 0.85)...
         Decision: yes (confidence: 0.98)
  ✅ Updated Apple Inc: estimated_annual_sales=$394100000000, total_funding=$0

...

================================================================================
BATCH ENRICHMENT COMPLETE
================================================================================
Total processed:  8
✅ Completed:      6
⏸️  Pending review: 1
⚠️  No data found:  0
⚠️  Low confidence: 0
⊘  Skipped:        1
❌ Errors:         0
================================================================================
```

### Example 2: Conservative with Manual Review
```bash
python backend/scripts/batch_enrich_orgs.py --id-range 1 50 --confidence 0.80 --output review.csv
```

This will:
1. Enrich orgs 1-50
2. Auto-approve only extractions with confidence >= 0.80
3. Flag items with confidence 0.70-0.80 for manual review in `review.csv`
4. Save results for analysis

### Example 3: Batch Run with Logging
```bash
# Run enrichment and capture all output
python backend/scripts/batch_enrich_orgs.py --id-range 100 200 --output results.csv > enrich.log 2>&1

# Monitor live progress
tail -f /tmp/batch_enrich.log
```

## Results and Output

### Console Output

The script logs progress in real-time with status emojis:
- ✅ `completed` — Successfully enriched and written to database
- ⏸️ `pending_review` — High-quality extraction but below confidence threshold
- ⚠️ `no_data_found` — Exa search returned no results
- ⚠️ `low_confidence` — LLM extracted data but confidence too low
- ⊘ `skipped` — Org not found in database or validation failed
- ❌ `error` — Exception during processing

### CSV Export Format

If you use `--output results.csv`, the file contains:

| Column | Description |
|--------|-------------|
| `org_id` | Organization ID |
| `org_name` | Organization name |
| `status` | Final status (completed, pending_review, error, etc.) |
| `stage` | Last workflow stage reached (validateOrgName, searchForEnrichmentData, etc.) |
| `decision` | Final decision (yes/no) |
| `confidence` | Confidence score (0.0-1.0) |
| `reason` | Human-readable explanation |
| `extracted_data_json` | Full JSON with annual_revenue, total_funding_raised, etc. |
| `error` | Exception message if status=error |

### Log File

All activity is logged to `/tmp/batch_enrich.log` for debugging.

## Workflow Stages

The ENRICH workflow runs 4 stages per organization:

1. **validateOrgName**: Confirm org exists in database via fuzzy matching
   - Returns: yes (org found) / no (org not found)

2. **searchForEnrichmentData**: Search Exa for funding and revenue data
   - Returns: yes (results found) / no (no search results)

3. **verifyExtractionResults**: Use GPT-4o-mini to parse search results
   - Extracts: annual_revenue, total_funding_raised, description, employees, headquarters, date_founded
   - Returns: yes (valid extraction) / no (invalid or missing data)

4. **enrichOrgDatabase**: Write approved data to `public.orgs`
   - Updates: estimated_annual_sales, funding, description, headquarters, employees, date_founded
   - Only runs if confidence >= threshold

## Database Impact

The script updates `public.orgs` table:

```sql
UPDATE public.orgs 
SET estimated_annual_sales = ?, 
    funding = ?,
    description = ?, 
    headquarters = ?,
    employees = ?,
    date_founded = ?,
    updated_at = now()
WHERE id = ?
```

Only null or zero fields are updated (existing data is preserved).

## Debugging

### Check Status of a Single Org

```bash
psql postgresql://pattern_factory:314159@localhost:5432/pattern-factory -c "SELECT id, name, estimated_annual_sales, funding, description, headquarters, employees FROM public.orgs WHERE id = 5;"
```

### Monitor Script Execution

```bash
# Watch live logs
tail -f /tmp/batch_enrich.log

# Or search for specific org
grep "Apple Inc" /tmp/batch_enrich.log
```

### Review Pending Items from CSV

```bash
# Show all pending review items
awk -F, '$3 == "pending_review" { print }' results.csv

# Count by status
cut -d, -f3 results.csv | sort | uniq -c
```

## Cost Considerations

- **Exa API**: ~$0.01-0.05 per search × number of orgs
  - 50 orgs ≈ $1.00-2.50
  - 100 orgs ≈ $2.00-5.00
  - 807 orgs ≈ $16.00-40.00 (estimate)

- **OpenAI API**: ~$0.001-0.005 per LLM call (gpt-4o-mini)
  - Minimal cost (less than Exa)

## Best Practices

### 1. Start Small
Test with a small sample first:
```bash
python backend/scripts/batch_enrich_orgs.py --id-range 1 10
```

### 2. Review Before Full Run
Check pending items from small batch, then decide on confidence threshold:
```bash
python backend/scripts/batch_enrich_orgs.py --id-range 1 50 --output sample.csv
# Review sample.csv for quality
```

### 3. Progressive Batches
Don't run all 807 at once; process in batches:
```bash
python backend/scripts/batch_enrich_orgs.py --id-range 1 100 --output batch1.csv
python backend/scripts/batch_enrich_orgs.py --id-range 101 200 --output batch2.csv
python backend/scripts/batch_enrich_orgs.py --id-range 201 300 --output batch3.csv
```

### 4. Monitor Results
Combine all results:
```bash
# Concatenate headers and data
(head -1 batch1.csv && tail -n +2 batch*.csv) > all_results.csv

# Analyze
awk -F, '$3 == "completed" { count++ } END { print "Completed:", count }' all_results.csv
```

## Troubleshooting

### "Database connection failed"
Check environment variables:
```bash
echo $PGHOST $PGPORT $PGUSER $PGDATABASE
psql -h 127.0.0.1 -U pattern_factory -d pattern-factory -c "SELECT 1"
```

### "EXA_API_KEY not configured"
Set the API key:
```bash
export EXA_API_KEY="your-exa-key"
python backend/scripts/batch_enrich_orgs.py --id-range 1 10
```

### "No orgs found to enrich in range [X, Y]"
Check if those org IDs exist:
```bash
psql postgresql://pattern_factory:314159@localhost:5432/pattern-factory -c "SELECT COUNT(*) FROM public.orgs WHERE id BETWEEN 1 AND 10;"
```

### Script hangs or is slow
- Normal: ~10-15 seconds per org due to Exa search + LLM latency
- If longer: check Exa API rate limits (may need to reduce --confidence to skip some)

## Next Steps

Once you're satisfied with batch results:

1. **Review pending items** in CSV with `pending_review` status
2. **Adjust confidence threshold** if needed
3. **Run larger batches** (e.g., all 807 orgs)
4. **Archive results** for audit trail
5. **Analyze enrichment quality** using exported CSVs
