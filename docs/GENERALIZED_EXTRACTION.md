# Generalized Entity Extraction in model.requestToExtractEntities

## Overview

The `model.requestToExtractEntities` agent has been generalized to perform comprehensive entity extraction from web content (posts, patterns, organizations, guests) using an LLM-powered pipeline.

**Key changes:**
- ✅ Reads system prompt from YAML (`CONTENT.EXTRACT_CONTENT`)
- ✅ Calls OpenAI with generalized extraction instructions
- ✅ Returns complete structured JSON (posts, patterns, orgs, guests, links)
- ✅ Maintains backward compatibility with URL parsing and HTTP fetch

## Architecture

### 1. System Prompt Loading
```python
def _get_extract_content_system_prompt(context_builder) -> Optional[str]:
```
- Loads the EXTRACT_CONTENT prompt from `pattern-factory.yaml`
- Fallback: Returns None if YAML loading fails
- Prompt contains detailed extraction rules for all entity types

### 2. HTTP Fetch & Content Retrieval
- Uses existing `_http_get_text()` helper
- Fetches up to 512KB of content
- Handles charset negotiation
- Returns (text, status_code, content_type)

### 3. LLM-Powered Entity Extraction
- **Model**: gpt-4o-mini
- **Temperature**: 0.2 (deterministic)
- **Timeout**: 30 seconds
- **Input**: URL + HTML content (up to 8KB)
- **Output**: JSON with all extracted entities

## JSON Output Structure

The agent returns this structure in the `reason` field (for HITL review):

```json
{
  "posts": [
    {
      "name": "Post Title",
      "description": "Post Subtitle/Description",
      "keywords": ["keyword1", "keyword2"],
      "content_url": "https://example.com/post",
      "content_source": "substack",
      "published_at": "Oct 24, 2025"
    }
  ],
  
  "patterns": [
    {
      "pattern_code": "PATTERN_NAME",
      "name": "Pattern Display Name",
      "description": "What this pattern is about",
      "kind": "pattern",
      "keywords": ["pattern", "keyword"],
      "content_url": "https://example.com/post",
      "content_source": "substack",
      "metadata": {"source": "LLM"},
      "highlights": ["Key insight 1", "Key insight 2"]
    }
  ],
  
  "orgs": [
    {
      "name": "Organization Name",
      "description": "What the org does",
      "keywords": ["biotech", "automation"],
      "content_url": "https://example.com/post",
      "content_source": "substack"
    }
  ],
  
  "guests": [
    {
      "name": "Person Name",
      "description": "Who they are",
      "job_description": "CEO of TechCorp",
      "keywords": ["ceo", "founder"],
      "content_url": "https://example.com/post",
      "content_source": "substack"
    }
  ],
  
  "pattern_post_link": [
    {
      "pattern_code": "PATTERN_NAME",
      "post_name": "Post Title"
    }
  ],
  
  "pattern_org_link": [
    {
      "pattern_code": "PATTERN_NAME",
      "org_name": "Organization Name"
    }
  ],
  
  "pattern_guest_link": [
    {
      "pattern_code": "PATTERN_NAME",
      "guest_name": "Person Name"
    }
  ]
}
```

## Extraction Rules (from YAML)

### Posts
- Extract title from `<h1 class="post-title">...</h1>`
- Extract description from `<h3 class="subtitle">...</h3>`
- Extract published date from meta divs (e.g., "Oct 24, 2025")
- Always set `content_source: "substack"`

### Patterns
- Extract conceptual patterns or anti-patterns explicitly mentioned
- `kind` must be "pattern" or "anti-pattern"
- `pattern_code` must be deterministic (uppercase with underscores)
- No hallucinated patterns

### Organizations
- Extract startups, CROs, labs, pharma companies mentioned
- No hallucinated orgs
- keywords must be lowercase

### Guests
- Extract identifiable people (CEOs, founders, speakers)
- Include org affiliation if mentioned
- If no org known, set org_name to null

### Link Tables
- No orphan links (must reference existing entities)
- Names must exactly match extracted entities
- pattern_code must reference an extracted pattern

## Error Handling

| Scenario | Response |
|----------|----------|
| No URL provided | NO (confidence 0.98) with usage hint |
| Invalid URL format | NO (confidence 0.98) with error message |
| HTTP non-200 | NO (confidence 0.95) with status code |
| YAML prompt not found | NO (confidence 0.70) with error |
| OpenAI API key missing | NO (confidence 0.70) with error |
| LLM returns invalid JSON | NO (confidence 0.60) with parse error |
| LLM extraction fails | NO (confidence 0.60) with error details |
| SUCCESS | NO (confidence 0.95) with JSON for HITL |

## Workflow Integration

```
User: "extract https://newsletter.dannylieberman.com/p/yes-size-matters"
         ↓
[model.Capo]
  └─ Recognizes "extract <url>" → returns yes
         ↓
[model.verifyRequest]
  └─ Validates URL present → returns yes
         ↓
[model.requestToExtractEntities]
  ├─ Fetch HTML from URL
  ├─ Load EXTRACT_CONTENT system prompt from YAML
  ├─ Call OpenAI with HTML content
  ├─ Parse JSON response
  ├─ Validate structure
  └─ Return NO with JSON for human review
         ↓
[HITL - Human Reviews JSON]
  ├─ Sees extracted posts, patterns, orgs, guests
  ├─ Can approve or modify
  └─ Submits for next agent
         ↓
[model.verifyUpsert] (future)
  └─ Validates payload for database safety
         ↓
[tool.executeSQL] (future)
  └─ Executes PostgreSQL upsert function
```

## Testing

### Test Files

1. **test_generalized_extraction.py**
   - ✅ Loads EXTRACT_CONTENT prompt from YAML
   - ✅ Validates JSON structure matches spec
   - ✅ Verifies all required arrays present
   - ✅ Checks link table consistency

2. **test_extract_flow.py**
   - ✅ Full workflow tests (backward compatible)
   - ✅ Title/subtitle/date extraction
   - ✅ Error handling

3. **test_url_extraction_bug.py**
   - ✅ Consecutive extractions use correct URL
   - ✅ Stale metadata clearing verified

### Run Tests

```bash
# Test generalized extraction
python test_generalized_extraction.py

# Test full extraction flow
python test_extract_flow.py

# Test URL extraction bug fix
python test_url_extraction_bug.py
```

All tests pass ✅

## Key Features

✅ **YAML-driven**: System prompt loads from pattern-factory.yaml CONTENT section  
✅ **Generalized**: Extracts any entity type with correct LLM instructions  
✅ **Structured output**: Complete JSON ready for database upsert  
✅ **Link integrity**: All linkages reference extracted entities  
✅ **Error resilient**: Graceful handling of network, API, and parsing failures  
✅ **Deterministic**: Temperature=0.2 for consistent extraction  
✅ **Backward compatible**: Existing tests still pass  
✅ **HITL-ready**: Returns decision=no with JSON for human review  

## Future Enhancements

1. **Multi-source support**: Extend for beehiiv, granola, X, podcast sources
2. **Custom entity types**: Allow configurable extraction targets via YAML
3. **LLM model switching**: Make model configurable (gpt-4, gpt-4-turbo, etc.)
4. **Batch extraction**: Process multiple URLs in single request
5. **Entity deduplication**: Smart matching for existing orgs/guests
6. **Confidence scoring**: Return confidence for each extracted entity

## Database Integration

The extracted JSON is passed to PostgreSQL function:
```sql
SELECT upsert_pattern_factory_entities(jsonb_payload);
```

The function handles:
- Upsert (insert or update) for all entity types
- Foreign key constraint validation
- Link table consistency
- Duplicate detection and merging

## Implementation Details

**File**: `backend/pitboss/agents.py`

**New functions:**
- `_get_extract_content_system_prompt(context_builder)` - Load YAML prompt
- Updated `agent_request_to_extract_entities()` - Generalized LLM extraction

**Dependencies:**
- OpenAI API (gpt-4o-mini)
- ContextBuilder (YAML loading)
- urllib (HTTP fetch)
- json (parsing)
- asyncio (concurrency)

**No new external dependencies added** ✅
