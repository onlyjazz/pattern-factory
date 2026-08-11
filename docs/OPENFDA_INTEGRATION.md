# OpenFDA Integration Service

Automated service to fetch FDA 510(k) device descriptions from the OpenFDA API and populate the `products.device_description` column in the database.

## Overview

The FEELGOOD agent flow requires device descriptions for competitive advantage analysis. This service provides:

1. **OpenFDA API Integration**: Queries the public OpenFDA 510(k) database using submission numbers
2. **Rate Limiting**: Respects public API limits (240 req/min) or uses authenticated rates (1000+ req/min)
3. **Retry Logic**: Handles transient failures with exponential backoff
4. **Batch Processing**: Fetches up to 10 descriptions concurrently per batch
5. **Database Updates**: Updates `products.device_description` with fetched data
6. **Audit Logging**: Records all operations in `system_log` table

## Architecture

### Components

**OpenFDAClient** (`backend/services/openfda_service.py`)
- HTTP client wrapper for OpenFDA API
- Rate limiting enforcer
- Retry handler with exponential backoff
- Response parsing and validation

**OpenFDAService** (`backend/services/openfda_service.py`)
- Orchestrates batch processing
- Manages database connections
- Coordinates API calls and database updates
- Returns detailed results with per-product status

**CLI Wrapper** (`backend/bin/openfda`)
- Command-line interface for manual and automated runs
- Argument parsing for product ID ranges
- Environment variable configuration

## Setup

### 1. Install Dependencies

The service requires `aiohttp` for async HTTP requests:

```bash
cd backend
pip install aiohttp  # Usually already in requirements.txt
```

### 2. Configure Environment

Set required environment variables in `.env`:

```env
# Required: PostgreSQL connection
DATABASE_URL=postgresql://pattern_factory:314159@localhost:5432/pattern-factory

# Optional: OpenFDA API key (for higher rate limits)
# Sign up free at: https://open.fda.gov/apis/
OPENFDA_API_KEY=your-api-key-here
```

### 3. Verify Database Connection

```bash
# Test PostgreSQL connection
psql postgresql://pattern_factory:314159@localhost:5432/pattern-factory -c "SELECT COUNT(*) FROM public.products;"
```

## Usage

### Command Line

```bash
# Populate up to 100 products without descriptions (default)
./backend/bin/openfda

# Populate specific product ID range
./backend/bin/openfda --range=1-50

# Populate specific product IDs
./backend/bin/openfda --product-ids=1,5,10

# Populate up to 200 products
./backend/bin/openfda --limit=200

# Dry-run simulation (check what would be processed)
# [Currently logs intended updates without persisting]
python backend/services/openfda_service.py --range=1-10
```

### Python API

```python
import asyncio
from backend.services.openfda_service import OpenFDAService

async def main():
    service = OpenFDAService(
        db_url="postgresql://pattern_factory:314159@localhost:5432/pattern-factory",
        api_key=None  # Optional
    )
    
    try:
        await service.initialize()
        
        # Populate specific products
        results = await service.populate_descriptions(
            product_ids=[1, 5, 10],
            limit=100
        )
        
        print(f"Success: {results['success']}")
        print(f"Failed: {results['failed']}")
        for detail in results['details']:
            print(f"  - Product {detail['product_id']}: {detail['status']}")
    
    finally:
        await service.cleanup()

asyncio.run(main())
```

## How It Works

### Batch Processing Flow

```
1. Get Products to Update
   ├─ Query: products without descriptions or specific IDs
   └─ Limit: configurable per run

2. Process in Batches (10 concurrent)
   ├─ Fetch descriptions from OpenFDA (rate-limited)
   ├─ Handle retries on rate limit (429)
   ├─ Handle not found (404)
   └─ Collect results

3. Update Database (per batch)
   ├─ Write device_description to products table
   ├─ Update updated_at timestamp
   └─ Log operation results

4. Log Results
   └─ Insert summary to system_log table
```

### Rate Limiting

**Without API Key** (240 req/min):
- 1 request every 0.25 seconds
- 10 concurrent requests per batch
- ~2.5 seconds per batch of 10

**With API Key** (1000+ req/min):
- Higher concurrency possible
- Much faster overall processing
- Free key from https://open.fda.gov/apis/

### Error Handling

| Status | Response | Action |
|--------|----------|--------|
| 200 | Success | Extract device_description and update |
| 404 | Not found | Log "Not found (404)" and continue |
| 429 | Rate limited | Retry with exponential backoff (up to 3x) |
| Timeout | Network error | Log "Request timeout" and continue |
| Other errors | Client/server | Log error and continue |

### Submission Number Format

Submission numbers must start with "K" followed by digits:
- Valid: `K191432`, `K220123`, `K230456`
- Invalid: `191432`, `IND-123`, empty string

Products with invalid submission numbers are skipped with error logged.

## OpenFDA API Details

### Endpoint

```
GET https://api.fda.gov/device/510k.json?search=submission_number:"K191432"
```

### Response Fields

```json
{
  "results": [
    {
      "submission_number": "K191432",
      "device_name": "Device Name",
      "applicant": "Company Name",
      "statement_or_description": "Device description text...",
      "product_code": "ABC",
      "...": "other fields"
    }
  ]
}
```

### Field Mapping

| OpenFDA Field | Product Column | Notes |
|---------------|----------------|-------|
| statement_or_description | device_description | Primary field for description |
| device_name | (not stored) | Informational |
| applicant | (not stored) | Informational |
| product_code | (not stored) | Informational |

## Results and Logging

### CLI Output

```
Initializing OpenFDA service...
✓ Database pool created
✓ OpenFDA HTTP client initialized
ℹ Using public OpenFDA API (240 req/min)
Processing 5 products...
✓ Product 1 (K191432): 245 chars
✓ Product 2 (K220123): 312 chars
✗ Product 3 (K190000): Not found (404)
✗ Product 4 (K210456): Request timeout
✓ Product 5 (K230789): 198 chars

✅ OpenFDA Population Complete
├─ Total:   5
├─ Success: 3
├─ Failed:  2
└─ Skipped: 0
✓ Connections closed
```

### Database Logging

Results are logged to `system_log` table:

```sql
SELECT * FROM public.system_log 
WHERE event_type = 'OPENFDA_POPULATION' 
ORDER BY created_at DESC 
LIMIT 1;
```

Details JSON structure:

```json
{
  "total": 5,
  "success": 3,
  "failed": 2,
  "skipped": 0,
  "details": [
    {
      "product_id": 1,
      "submission_number": "K191432",
      "status": "success",
      "description_length": 245,
      "timestamp": "2026-08-11T12:34:56.789012"
    },
    {
      "product_id": 3,
      "submission_number": "K190000",
      "status": "failed",
      "error": "Not found (404)",
      "timestamp": "2026-08-11T12:34:57.123456"
    }
  ]
}
```

## Integration with FEELGOOD Flow

Once `device_description` is populated, the FEELGOOD agent flow can:

1. **Validate product exists** and has submission_number
2. **Extract device description** for web search
3. **Search for superiority claims** using Exa API
4. **Extract competitive advantages** using GPT-4o
5. **Update products.superiority** with findings

### Example FEELGOOD Flow

```
Product ID: 42
├─ device_description: "Advanced monitoring device using AI analysis"
├─ Exa search: "how is advanced monitoring device using AI analysis from Medtronic superior to competing solutions"
├─ Results: [article1.url, article2.url, article3.url]
├─ GPT-4o extraction: "Claims superior real-time monitoring with 99.9% accuracy..."
└─ Store: products.superiority = "Claims superior real-time monitoring..."
```

## Testing

### Test with Sample Products

```bash
# Populate a small batch first (products 1-5)
./backend/bin/openfda --product-ids=1,2,3,4,5

# Check results
psql -h localhost -U pattern_factory -d pattern-factory -c \
  "SELECT id, submission_number, LENGTH(device_description) as desc_length FROM public.products WHERE id <= 5;"
```

### Verify in Database

```sql
-- Check products with descriptions populated
SELECT id, submission_number, device_description 
FROM public.products 
WHERE device_description IS NOT NULL AND LENGTH(device_description) > 0
LIMIT 5;

-- Check system_log for last run
SELECT id, event_type, created_at, details 
FROM public.system_log 
WHERE event_type = 'OPENFDA_POPULATION'
ORDER BY created_at DESC 
LIMIT 1;
```

### Monitor OpenFDA API

```bash
# Simple health check (no credentials needed)
curl -s "https://api.fda.gov/device/510k.json?search=submission_number:\"K191432\"" | jq '.results[0].statement_or_description'
```

## Troubleshooting

### No Results Found

**Problem**: All products show "Not found (404)" errors.

**Causes**:
- Submission numbers not in OpenFDA database
- Submission numbers with incorrect format
- OpenFDA API is down

**Solution**:
```bash
# Verify submission number format
psql -h localhost -U pattern_factory -d pattern-factory -c \
  "SELECT DISTINCT submission_number FROM public.products LIMIT 5;"

# Test a known K-number manually
curl -s "https://api.fda.gov/device/510k.json?search=submission_number:\"K191432\"" | jq '.results | length'
```

### Rate Limit (429) Errors

**Problem**: Service keeps hitting rate limit.

**Solution**:
1. Reduce batch size or concurrent requests
2. Add OpenFDA API key for higher limits
3. Run during off-peak hours
4. Increase `RATE_LIMIT_DELAY` in code

### Connection Timeout

**Problem**: Database or OpenFDA requests timing out.

**Solution**:
```bash
# Check database connectivity
psql postgresql://pattern_factory:314159@localhost:5432/pattern-factory -c "SELECT 1;"

# Check OpenFDA API accessibility
curl -s https://api.fda.gov/device/510k.json -o /dev/null -w "%{http_code}\n"

# Increase timeout in openfda_service.py
REQUEST_TIMEOUT = 120  # seconds (was 60)
```

## Performance Notes

- **Typical throughput**: 4-6 descriptions per second (without API key)
- **100 products**: ~20 seconds
- **1000 products**: ~3-5 minutes
- **10000 products**: ~30-50 minutes

With authenticated API key, rates scale up to 10-15 per second.

## Security Notes

1. **API Key**: Store in `.env` file (not in code or git)
2. **Database**: Uses SSL if connection string includes `?sslmode=require`
3. **Logging**: Sensitive data (submission numbers) logged only in system_log table
4. **Public API**: No authentication required for public OpenFDA endpoint

## References

- OpenFDA 510(k) API: https://open.fda.gov/apis/device/510k/
- Free API Key Signup: https://open.fda.gov/apis/
- OpenFDA Documentation: https://api.fda.gov/
- Submission Number Format: https://www.fda.gov/medical-devices/premarket-notification-510k/what-k-number

## Future Enhancements

- [ ] Incremental population (skip already-populated products)
- [ ] Parallel batch processing with multiple services
- [ ] Webhook callback on completion
- [ ] GraphQL subscription for real-time progress
- [ ] Cache OpenFDA results to reduce API calls
- [ ] Support for other FDA device data (PMA, HDE, etc.)
