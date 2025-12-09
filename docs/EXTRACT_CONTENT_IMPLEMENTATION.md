# Extract Content Flow Implementation Summary

## Overview

The Pattern Factory now has a complete end-to-end CONTENT flow for extracting entities (orgs, guests, patterns, posts) from web content and upserting them into the database.

## Complete Flow

```
User Input: "extract <url>"
    ↓
model.LanguageCapo (pre-workflow router)
  • Routes to CONTENT workflow
  • decision=yes, verb=CONTENT
    ↓
model.Capo_content (CONTENT entry point)
  • Validates "extract <url>" format
  • decision=yes → model.verifyRequest
    ↓
model.verifyRequest_content
  • Checks URL is present and valid
  • decision=yes → model.requestToExtractEntities
    ↓
model.requestToExtractEntities ⭐
  • Fetches URL content via HTTP GET
  • Calls EXTRACT_CONTENT LLM prompt (from YAML)
  • Parses JSON response
  • Stores extracted_entities in message_body
  • Returns user-friendly summary (post name, date, entities)
  • decision=yes → model.verifyUpsert
    ↓
model.verifyUpsert ⭐
  • Validates extracted_entities structure
  • Checks required fields (name, kind, etc.)
  • Validates link table consistency (no orphan references)
  • Safety checks (no SQL injection patterns)
  • Semantic validation (URL/source consistency, timestamps)
  • decision=yes → tool.executeSQL
    ↓
tool.executeSQL (CONTENT branch) ⭐
  • Detects _verb=CONTENT
  • Calls ExecuteUpsertTool
  • Executes: CALL upsert_pattern_factory_entities($1::jsonb, NULL::jsonb)
  • Returns success message
  • decision=yes → sendMessageToChat (terminal)
```

## Key Components Implemented

### 1. agent_verify_upsert (agents.py)

**Validates the extracted entity payload:**
- ✅ Structural validity (all required arrays exist)
- ✅ Required fields (orgs/guests/posts have `name`; patterns have `name` + `kind`)
- ✅ Link table consistency (pattern_post_link, pattern_org_link, pattern_guest_link reference actual entities)
- ✅ Safety validation (detects SQL injection patterns)
- ✅ Semantic checks (URL/source consistency, timestamp validation)

**Decision Logic:**
- `decision=yes` → Routes to `tool.executeSQL` for upsert
- `decision=no` → Routes to `sendMessageToChat` with error details for human review

### 2. ExecuteUpsertTool (tools.py)

**Executes the PostgreSQL upsert procedure:**
```python
class ExecuteUpsertTool(Tool):
    async def execute(self, jsonb_payload: Dict[str, Any], **kwargs):
        payload_json = json.dumps(jsonb_payload)
        async with self.db_pool.acquire() as conn:
            result = await conn.fetchrow(
                "CALL upsert_pattern_factory_entities($1::jsonb, NULL::jsonb)",
                payload_json
            )
```

**Procedure Call Syntax:**
```sql
CALL upsert_pattern_factory_entities(
    '{"orgs": [...], "guests": [...], ...}'::jsonb,
    NULL::jsonb
)
```

**Features:**
- Parameterized queries (prevents SQL injection)
- Async database operations via asyncpg
- Proper error handling and logging
- Registered in ToolRegistry for easy access

### 3. Dual-Flow agent_execute_sql (agents.py)

**Handles both RULE and CONTENT workflows:**

```python
verb = message_body.get("_verb", "RULE").upper()

if verb == "CONTENT":
    # Execute upsert: CALL upsert_pattern_factory_entities(...)
    upsert_res = await tool_registry.execute("execute_upsert", jsonb_payload=extracted_entities)
else:
    # RULE flow: Create materialized view
    table_res = await tool_registry.execute("data_table", sql_query=sql_query, ...)
```

**Responsibilities:**
- Branch on verb to handle both workflows
- Extract dependencies (tool_registry, extracted_entities or sql_query)
- Call appropriate tool
- Store results in message_body
- Return decision and summary

### 4. Supervisor Integration (supervisor.py)

**Passes workflow context to agents:**
```python
# Line 185: Pass verb into message_body for agent flow detection
env.messageBody["_verb"] = verb_str  # "RULE" or "CONTENT"
```

This allows `agent_execute_sql` to detect which branch to take.

### 5. Workflow Configuration (workflow.py)

**Already configured (no changes needed):**
```
CONTENT Flow:
  model.Capo → model.verifyRequest → model.requestToExtractEntities
    → model.verifyUpsert → tool.executeSQL → sendMessageToChat
```

## Extracted Entities Structure

The LLM produces a payload with this structure:

```json
{
  "orgs": [
    {
      "name": "Medable",
      "description": "...",
      "content_url": "https://...",
      "content_source": "substack"
    }
  ],
  "guests": [
    {
      "name": "Pamela Tenaerts",
      "description": "...",
      "job_description": "Chief Medical Officer",
      "org_name": "Medable",
      "content_url": "https://...",
      "content_source": "substack"
    }
  ],
  "posts": [
    {
      "name": "Dissent is an act of faith",
      "description": "...",
      "content_url": "https://...",
      "content_source": "substack",
      "published_at": "Sep 26, 2025"
    }
  ],
  "patterns": [
    {
      "name": "Boss is Stuck",
      "description": "...",
      "kind": "anti-pattern",
      "content_source": "substack"
    }
  ],
  "pattern_post_link": [
    {
      "pattern_name": "Boss is Stuck",
      "post_name": "Dissent is an act of faith"
    }
  ],
  "pattern_org_link": [
    {
      "pattern_name": "Boss is Stuck",
      "org_name": "Medable"
    }
  ],
  "pattern_guest_link": [
    {
      "pattern_name": "Boss is Stuck",
      "guest_name": "Pamela Tenaerts"
    }
  ]
}
```

## User-Facing Output

The extraction agent returns a clean summary instead of raw JSON:

```
[YES] (96%)
Post: 'Dissent is an act of faith' (Sep 26, 2025)
Organizations: Medable
Guests: Pamela Tenaerts
Patterns: Boss is Stuck
```

The full payload is preserved internally for downstream processing.

## Error Handling

**Graceful degradation at each stage:**

1. **agent_request_to_extract_entities fails**
   - Invalid URL → Return NO with error
   - HTTP error → Return NO with status code
   - LLM failure → Return NO with error message
   - Missing YAML prompt → Return NO with error

2. **agent_verify_upsert fails**
   - Structural issues → Return NO with details
   - Missing required fields → Return NO with field path
   - Orphan references → Return NO with reference details
   - Safety violations → Return NO with violation type

3. **agent_execute_sql (CONTENT) fails**
   - Missing payload → Return NO with error
   - Procedure call fails → Return NO with database error

## Files Modified

### backend/pitboss/agents.py
- Implemented `agent_verify_upsert()` with comprehensive validation
- Modified `agent_execute_sql()` to handle both RULE and CONTENT flows
- Updated `agent_request_to_extract_entities()` to return user-friendly summary
- Fixed `agent_capo_content()` to be deterministic (removed random fallback)
- Removed unused `random` import

### backend/pitboss/tools.py
- Added `ExecuteUpsertTool` class for calling the upsert procedure
- Registered `ExecuteUpsertTool` in `ToolRegistry._register_default_tools()`

### backend/pitboss/supervisor.py
- Pass `_verb` into message_body for agent flow detection (line 185)

### backend/pitboss/workflow.py
- No changes (flow was already properly configured)

## Testing Checklist

✅ Extract valid URL → Entities extracted correctly
✅ LLM returns proper JSON structure → Parsed correctly
✅ verifyUpsert validates structure → Passes validation
✅ verifyUpsert checks links → Rejects orphan references
✅ executeSQL detects CONTENT → Calls upsert procedure
✅ Database procedure receives payload → Upserts entities
✅ User sees clean summary → Not exposed to raw JSON

## Next Steps

Optional enhancements:
- Add HITL review step before upsert (return `decision=no` from `verifyUpsert` to show validated payload for approval)
- Add duplicate detection (warn if entities already in database)
- Add confidence scoring for extracted entities
- Add logging of all upsertal operations to audit table
- Add batch processing for multiple URLs

## Notes

- The `ExecuteUpsertTool` only calls the procedure; the procedure itself (`upsert_pattern_factory_entities`) handles all database logic
- Parameterized queries prevent SQL injection at the asyncpg level
- All entity relationships are validated before database calls
- The flow is designed for async/await throughout for performance
- Comprehensive logging at DEBUG, INFO, and ERROR levels for troubleshooting
