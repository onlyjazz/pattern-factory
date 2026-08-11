# FEELGOOD Agent Flow Implementation

## Overview

The FEELGOOD verb enables extraction and storage of competitive advantage claims for FDA-approved medical devices. It uses a multi-agent workflow to:

1. Validate products exist in the database
2. Search the web for competitive information using Exa API
3. Extract superiority claims using GPT-4o LLM
4. Store results in the products table

## Architecture

### Verb Registration

Added `FEELGOOD` to the `Verb` enum in `backend/pitboss/envelope.py`:

```python
class Verb(str, Enum):
    FEELGOOD = "FEELGOOD"  # Extract product superiority claims from web search
```

### Workflow Definition

Defined in `backend/pitboss/workflow.py`:

```
model.Capo (validation)
  ↓
model.validateProductId (database lookup)
  ↓
model.searchForSuperiority (web search with Exa)
  ↓
model.extractSuperiorityClaim (LLM analysis)
  ↓
tool.updateProductSuperiority (database update)
  ↓
sendMessageToChat (return results)
```

### Agent Implementations

Created `backend/pitboss/feelgood.py` with four agents:

#### 1. `agent_validate_product_id`
- Extracts product ID from message
- Queries database for product record
- Validates required fields (company, device)
- Returns product data for next agents

#### 2. `agent_search_for_superiority`
- Uses Exa API to search the web
- Query: "how is the {device} from {company} superior to competing solutions"
- Retrieves top 3 results with URLs, titles, and snippets
- Returns search results for LLM analysis

#### 3. `agent_extract_superiority_claim`
- Passes search results to GPT-4o
- Prompts LLM to extract competitive advantages
- Produces 2-3 sentence superiority narrative
- Confidence threshold: 0.85+

#### 4. `tool_update_product_superiority`
- Updates products.superiority column
- Logs operation to system_log table
- Returns success/failure

### Database Schema

Created migration `backend/db/20260811-add-product-details.sql`:

```sql
ALTER TABLE public.products
ADD COLUMN IF NOT EXISTS device_description TEXT;

ALTER TABLE public.products
ADD COLUMN IF NOT EXISTS superiority TEXT;
```

**Fields:**
- `device_description`: Populated from OpenFDA API (statement_or_description field)
- `superiority`: Populated by FEELGOOD flow (competitive advantages)

## Usage

### 1. Single Product

```bash
# Send FEELGOOD verb with product ID
POST /api/endpoint with:
{
  "verb": "FEELGOOD",
  "messageBody": {
    "product_id": 42,
    "raw_text": "feelgood 42"
  }
}
```

### 2. Batch Processing

```bash
# Process products 1-50
cd backend
python -m bin.feelgood --products 1-50

# Process specific products
python -m bin.feelgood --products 1,5,10,20

# Dry run (validation only)
python -m bin.feelgood --products 1-50 --dry-run
```

### 3. Populate device_description from OpenFDA

```bash
# Fetch descriptions for products 1-50
cd backend
python data/fetch_openfda_descriptions.py --range=1-50

# Fetch for specific products
python data/fetch_openfda_descriptions.py --product-ids=1,5,10
```

## Environment Variables

Required:
- `DATABASE_URL`: PostgreSQL connection (e.g., `postgresql://user:pass@localhost/dbname`)
- `OPENAI_API_KEY`: OpenAI GPT-4o API key
- `EXA_API_KEY`: Exa search API key (required for web search)

## Message Protocol

### Request

```json
{
  "type": "request",
  "version": "1.1",
  "session_id": "sess-xyz",
  "request_id": "req-001",
  "verb": "FEELGOOD",
  "messageBody": {
    "product_id": 42,
    "raw_text": "feelgood 42"
  }
}
```

### Response Flow

1. **Capo (validation)**: "Is this a valid feelgood request?"
   - Decision: yes/no
   
2. **validateProductId**: "Does product exist?"
   - Extracts product ID from message
   - Validates in database
   - Stores product record in messageBody

3. **searchForSuperiority**: "Find competitive info on web?"
   - Constructs Exa search query
   - Retrieves top results
   - Stores search_results in messageBody

4. **extractSuperiorityClaim**: "Extract key advantages?"
   - Calls GPT-4o with search results
   - Produces 2-3 sentence claim
   - Stores superiority_claim in messageBody

5. **updateProductSuperiority**: "Update database?"
   - Writes to products.superiority column
   - Logs to system_log table
   - Returns success

## Example: Product Superiority Claim

For the BriefCase-Triage device from AIdoc Medical:

**Search Query:**
```
how is the BriefCase-Triage from AIdoc Medical superior to competing or existing solutions
```

**Extracted Claim:**
```
Aidoc's BriefCase-Triage solutions stand out from competing single-condition imaging tools 
by utilizing a broad foundation model framework (CARE™) that covers double-digit acute 
pathologies in a single workflow, delivering significantly higher sensitivity, fewer false 
alerts, and deeper integration via the Aidoc platform.
```

## Files Created/Modified

### Created
- `backend/db/20260811-add-product-details.sql` - Schema migration
- `backend/pitboss/feelgood.py` - Agent implementations
- `backend/bin/feelgood` - Batch CLI script
- `backend/data/fetch_openfda_descriptions.py` - OpenFDA population script
- `FEELGOOD_IMPLEMENTATION.md` - This document

### Modified
- `backend/pitboss/envelope.py` - Added FEELGOOD verb
- `backend/pitboss/workflow.py` - Added FEELGOOD workflow
- `backend/pitboss/agents.py` - Imported and registered feelgood agents
- `backend/pitboss/supervisor.py` - Updated verb validation

## Integration with Pitboss

The FEELGOOD flow integrates seamlessly with the existing Pitboss supervisor:

1. **Verb Routing**: Supervisor routes FEELGOOD messages to appropriate agents
2. **Decision Trees**: Workflow engine handles branching (yes/no decisions)
3. **Agent Registry**: All agents registered in AGENT_REGISTRY
4. **Message Protocol**: Follows standard v1.1 envelope format
5. **Logging**: All operations logged to system_log table

## Error Handling

### Graceful Degradation

- **No Exa API key**: Search fails, returns "no" decision, alerts user
- **Search returns no results**: Extraction fails, tries next product
- **LLM extraction too short**: Validates minimum text length (20 chars)
- **Database connection fails**: Logs error, continues to next product
- **Invalid product ID**: Validates and returns helpful error message

### Batch Operation

- Processes each product independently
- Records failures in system_log with error details
- Continues processing remaining products on individual failures
- Returns summary: success count, failed count, total processed

## Performance Considerations

### Concurrency

- OpenFDA fetch script: 10 concurrent requests per batch
- FEELGOOD batch: Sequential product processing (2s pause between)
- Database pool: Min 1, Max 5 connections

### Timeouts

- OpenFDA API: 60 second timeout per request
- Web search (Exa): 70 second timeout per search
- LLM (GPT-4o): Default OpenAI timeout

### Rate Limiting

- OpenFDA: 240 requests/minute (public), higher with API key
- Exa: Check API limits in documentation
- OpenAI: Standard rate limits apply

## Testing

### Unit Testing

```bash
# Test individual agents
python -c "
from backend.pitboss.feelgood import agent_validate_product_id
import asyncio

message_body = {'product_id': 1, '_db': db_connection}
result = asyncio.run(agent_validate_product_id(message_body))
print(result)
"
```

### Integration Testing

```bash
# Single product through supervisor
python -m bin.feelgood --product 1 --dry-run

# Batch validation
python -m bin.feelgood --products 1-10 --dry-run

# Full execution (requires APIs)
python -m bin.feelgood --products 1-5
```

## Future Enhancements

1. **HITL (Human-in-the-Loop)**: Present LLM-extracted claims for user approval before database update
2. **Confidence Scoring**: Return confidence metrics with each claim
3. **Competitor Analysis**: Extract specific competitor names and advantages
4. **Historical Tracking**: Store superiority claim history with timestamps
5. **Caching**: Cache web search results for identical queries
6. **Bulk Import**: Support importing pre-computed superiority claims
7. **API Integration**: Create REST endpoint for on-demand feelgood requests

## Troubleshooting

### Web search returns no results

**Issue**: Exa search fails for product
**Solution**:
- Check Exa API key in environment
- Verify product company and device names are populated
- Try fallback to device_name only (no company)

### LLM extraction produces empty/short claims

**Issue**: GPT-4o returns insufficient text
**Solution**:
- Check OPENAI_API_KEY validity
- Verify search results contain relevant information
- Adjust LLM prompt in `agent_extract_superiority_claim`

### Database updates fail

**Issue**: Cannot write to products table
**Solution**:
- Verify DATABASE_URL connection string
- Check database permissions for user
- Ensure schema migration has been applied
- Verify columns exist: `device_description`, `superiority`

### Products not found in validation

**Issue**: Product ID validation fails
**Solution**:
- Verify product ID exists in database
- Check product record has company and device fields
- Query directly: `SELECT * FROM public.products WHERE id = ?`

## Related Documentation

- **Message Protocol**: See `backend/pitboss/envelope.py` for v1.1 spec
- **Workflow Engine**: See `backend/pitboss/workflow.py` for decision tree system
- **Agent Architecture**: See `backend/pitboss/agents.py` for agent routing
- **OpenFDA API**: https://open.fda.gov/device/510k/
- **Exa Search**: https://www.exa.ai/ (documentation in account dashboard)

## Author Notes

This implementation follows the existing patterns in Pattern Factory:

- Agent-based workflow matching ENRICH and GENERATE flows
- Message envelope protocol for frontend-backend communication
- Decision tree branching for complex workflows
- Comprehensive error handling and logging
- Batch processing via CLI tools
- Database integration with system_log auditing

The FEELGOOD flow can be extended to support:
- Interactive HITL approval step
- Multiple search strategies (Google, DuckDuckGo, scholarly)
- Structured claim extraction (JSON with reasoning)
- Competitive intelligence aggregation
