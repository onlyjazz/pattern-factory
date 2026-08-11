# FEELGOOD Agent Flow Implementation

Complete guide to running the FEELGOOD agent flow for extracting product competitive advantages from web searches.

## Overview

The FEELGOOD workflow extracts competitive advantage claims for FDA-cleared AI-enabled medical devices by:

1. **Validating** the product exists in the database
2. **Searching** the web using Exa API for competitive advantage information
3. **Extracting** claims using GPT-4o LLM analysis
4. **Storing** superiority claims in the products table

## Workflow Agents

### 1. model.validateProductId

**Responsibility**: Verify product exists in database with required fields.

**Input**: `product_id` (int) from message body

**Output**: 
- Success: Product data stored in `message_body["product"]`
- Failure: Error reason logged

**Required Fields**:
- `company` - Device manufacturer/applicant
- `device` - Device name
- `device_description` - Already populated by FDA Primary Source service

### 2. model.searchForSuperiority

**Responsibility**: Search the web for competitive advantage information using Exa API.

**Input**: 
- Product data (company, device, indicated_use, device_description)
- Exa API key from environment

**Query Construction**:
```
"how is the {device_description} from {company} superior to competing or existing solutions"
```

**Output**:
- Search results stored in `message_body["search_results"]`
- Top 3 neural search results with URLs, titles, snippets

**Requirements**:
- `EXA_API_KEY` environment variable set
- `exa-py` package installed

### 3. model.extractSuperiorityClaim

**Responsibility**: Parse search results and extract competitive advantage claims using GPT-4o.

**Input**:
- Product data (device, company, indicated_use)
- Search results (3 URLs with content snippets)

**Prompt**:
Analyzes search results for how the product differentiates from competitors, focusing on:
- Technical superiority
- Clinical benefits
- Market differentiation
- Innovation claims

**Output**:
- Superiority claim (2-3 sentences) stored in `message_body["superiority_claim"]`
- Confidence score (0.85 typical)

**Requirements**:
- `OPENAI_API_KEY` environment variable set
- OpenAI `gpt-4o` model access

### 4. tool.updateProductSuperiority

**Responsibility**: Write superiority claim to database and log operation.

**Input**:
- `product_id` (int)
- `superiority_claim` (str) extracted by previous agent

**Database Update**:
```sql
UPDATE public.products
SET superiority = $1, updated_at = NOW()
WHERE id = $2
```

**Logging**:
- Records operation to `system_log` table
- Event type: `FEELGOOD_COMPLETE`
- Details: claim length, timestamp

## Service Implementation

### FEELGOODService

Main orchestration class that runs the workflow.

**Initialization**:
```python
service = FEELGOODService(db_url="postgresql://...")
await service.initialize()
```

**Running the flow**:
```python
# Single product
result = await service.run_feelgood_flow(product_dict)

# Multiple products
results = await service.process_products(limit=100)
```

**Cleanup**:
```python
await service.cleanup()
```

## Usage

### Command Line

```bash
# Process up to 100 products without superiority claims
./backend/bin/feelgood

# Process specific products
./backend/bin/feelgood --product-ids=1,5,10

# Process product range
./backend/bin/feelgood --range=1-50

# Process custom limit
./backend/bin/feelgood --limit=200
```

### Python API

```python
import asyncio
from backend.services.feelgood_service import FEELGOODService

async def extract_superiorities():
    service = FEELGOODService(
        db_url="postgresql://pattern_factory:314159@localhost:5432/pattern-factory"
    )
    
    try:
        await service.initialize()
        
        # Process 10 products
        results = await service.process_products(limit=10)
        
        print(f"Success: {results['success']}")
        print(f"Failed: {results['failed']}")
        
        for detail in results['details']:
            print(f"Product {detail['product_id']}: {detail['status']}")
    
    finally:
        await service.cleanup()

asyncio.run(extract_superiorities())
```

## Environment Setup

### Required Environment Variables

```bash
# PostgreSQL connection
export DATABASE_URL="postgresql://pattern_factory:314159@localhost:5432/pattern-factory"

# Exa API (for web search)
export EXA_API_KEY="your-exa-api-key"

# OpenAI (for GPT-4o)
export OPENAI_API_KEY="your-openai-api-key"
```

### Get API Keys

**Exa API**:
- Sign up at https://exa.ai
- Get API key from dashboard
- Used for neural semantic web search

**OpenAI API**:
- Sign up at https://openai.com
- Create API key in account settings
- Requires `gpt-4o` model access

### Dependencies

```bash
# Already in requirements.txt:
pip install exa-py openai asyncpg python-dotenv
```

## Data Flow

```
Prerequisites:
  1. device_description populated (via FDA Primary Source service)
  2. indicated_use already in database (from product load)

FEELGOOD Flow:
  Product → model.validateProductId
           → model.searchForSuperiority (Exa API)
           → model.extractSuperiorityClaim (GPT-4o)
           → tool.updateProductSuperiority (write to DB)
           → products.superiority column populated
```

## Example Execution

### Input Product

```sql
SELECT id, submission_number, device, company, indicated_use, device_description
FROM public.products WHERE id = 6;

id  | submission_number | device                          | company               | indicated_use | device_description
----|-------------------|---------------------------------|-----------------------|---------------|-------------------------------------
  6 | K253595           | EPIQ Series Diagnostic...       | Philips Ultrasound    | Cardiology    | EPIQ Series Diagnostic... from Philips
```

### Exa Search Query

```
"how is the EPIQ Series Diagnostic Ultrasound System, Affiniti from Philips Ultrasound superior to competing or existing solutions"
```

### Search Results (Top 3)

1. Philips.com marketing page - Advantages of Affiniti technology
2. Medical device review article - Performance comparison study
3. Hospital procurement case study - Selection of Philips system

### GPT-4o Extracted Claim

```
The EPIQ Series with Affiniti technology delivers enhanced cardiac imaging 
through AI-powered image optimization, providing superior spatial resolution and 
reduced artifact compared to legacy ultrasound systems, enabling faster diagnosis 
and improved patient outcomes in cardiology applications.
```

### Database Update

```sql
UPDATE public.products
SET superiority = 'The EPIQ Series with Affiniti technology...',
    updated_at = NOW()
WHERE id = 6;
```

## Monitoring

### Check Progress

```bash
# Monitor system_log for FEELGOOD operations
SELECT id, event_type, created_at, details 
FROM public.system_log 
WHERE event_type IN ('FEELGOOD_COMPLETE', 'FEELGOOD_BATCH_COMPLETE')
ORDER BY created_at DESC 
LIMIT 10;
```

### Count Populated Products

```sql
-- How many have superiority claims
SELECT COUNT(*) FROM public.products 
WHERE superiority IS NOT NULL AND LENGTH(superiority) > 0;

-- Sample populated products
SELECT id, submission_number, device, superiority 
FROM public.products 
WHERE superiority IS NOT NULL 
LIMIT 5;
```

## Error Handling

### Common Issues

**Issue**: "No products to process"
- Products exist but already have superiority claims
- Check: `SELECT COUNT(*) FROM public.products WHERE superiority IS NULL`

**Issue**: "EXA_API_KEY not set"
- Solution: `export EXA_API_KEY="your-key"`

**Issue**: "OPENAI_API_KEY not set"
- Solution: `export OPENAI_API_KEY="your-key"`

**Issue**: "Product not found in database"
- Solution: Run FDA Primary Source service first to populate device_description

**Issue**: "No search results found"
- Cause: Device description too vague
- Solution: Verify device_description is meaningful

**Issue**: "Exa API rate limit"
- Solution: Add small delays between product processing
- Service automatically adds 0.5 second pause between products

## Performance

- **Per product**: 5-15 seconds (depends on Exa + GPT-4o response times)
- **100 products**: ~10-25 minutes
- **Parallelizable**: Can run multiple service instances on different product ranges

## Architecture

### Components

**FEELGOODService** - Orchestrator
- Manages database connections
- Runs workflow engine
- Tracks results

**WorkflowEngine** - Decision tree execution
- Defines FEELGOOD workflow nodes
- Routes decisions (yes/no) to next agent
- Tracks execution path

**Agents** (in `pitboss/feelgood.py`)
- Async agent functions
- Return: (decision: yes|no, confidence: 0.0-1.0, reason: str)

**External APIs**
- Exa API: Neural semantic web search
- OpenAI API: GPT-4o LLM analysis

### Message Body Flow

The `message_body` dict flows through agents, accumulating data:

```python
message_body = {
    "product_id": 6,
    "submission_number": "K253595",
    "product": {...},  # Added by validateProductId
    "search_query": "how is the...",  # Added by searchForSuperiority
    "search_results": [...],  # Added by searchForSuperiority
    "superiority_claim": "The EPIQ...",  # Added by extractSuperiorityClaim
    "_db": pool,  # Database connection
    "verb": "FEELGOOD"
}
```

## Integration with Complete Pipeline

The FEELGOOD flow is the final step in product enrichment:

```
1. Products loaded from FDA CSV
   ↓
2. FDA Primary Source service populates device_description
   ↓
3. FEELGOOD flow extracts superiority claims
   ↓
4. Fully enriched products ready for analysis
```

All three stages use the same products table and log to system_log for audit trail.

## Testing

### Dry Run (Single Product)

```bash
./backend/bin/feelgood --product-ids=6 --limit=1
```

### Small Batch (5 Products)

```bash
./backend/bin/feelgood --limit=5
```

### Production Run (All Unpopulated)

```bash
./backend/bin/feelgood
```

## Summary

The FEELGOOD agent flow provides an automated pipeline to extract competitive advantage claims for FDA-cleared AI-enabled medical devices using:

✅ **Exa API** - Neural semantic web search for relevant information
✅ **GPT-4o** - LLM-based extraction of competitive advantages
✅ **Workflow Engine** - Decision-tree agent orchestration
✅ **Pitboss Supervisor** - Async multi-agent coordination
✅ **System Logging** - Complete audit trail in system_log table

Once device_description is populated (via FDA Primary Source service), FEELGOOD can immediately extract superiority claims for all products.
