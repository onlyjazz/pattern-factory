# Entity Upsert Flow Implementation

## Overview

The `tool.executeSQL` agent now handles both RULE and CONTENT workflows. When called from the CONTENT flow, it executes the PostgreSQL `upsert_pattern_factory_entities` procedure instead of creating a materialized view.

## Flow Detection

The supervisor passes the workflow verb (`_verb`) into `message_body` at line 185 of `supervisor.py`:

```python
# Pass verb into message_body for agents to detect flow (RULE vs CONTENT)
env.messageBody["_verb"] = verb_str
```

The `agent_execute_sql` function uses this to branch:

```python
verb = message_body.get("_verb", "RULE").upper()

if verb == "CONTENT":
    # Execute upsert procedure
else:
    # Create materialized view (RULE flow)
```

## CONTENT Flow Procedure Call

### 1. Extracted Entities Payload

Before `executeSQL` is called, the extraction pipeline produces:

```python
extracted_entities = {
    "orgs": [...],
    "guests": [...],
    "posts": [...],
    "patterns": [...],
    "pattern_post_link": [...],
    "pattern_org_link": [...],
    "pattern_guest_link": [...]
}
```

This is stored in `message_body["extracted_entities"]` by `agent_request_to_extract_entities`.

### 2. Validation

`agent_verify_upsert` validates the payload for:
- Structural validity (all required arrays present)
- Required fields (orgs/guests/posts need `name`; patterns need `name` + `kind`)
- Link table consistency (no orphan references)
- Safety (no SQL injection patterns)
- Semantic checks (URL/source consistency, valid timestamps)

### 3. Procedure Execution

The `ExecuteUpsertTool` (in `tools.py`) executes the procedure:

```python
async def execute(self, jsonb_payload: Dict[str, Any], **kwargs):
    payload_json = json_module.dumps(jsonb_payload)
    
    async with self.db_pool.acquire() as conn:
        result = await conn.fetchrow(
            "CALL upsert_pattern_factory_entities($1::jsonb, NULL::jsonb)",
            payload_json
        )
```

The syntax maps to:
```sql
CALL upsert_pattern_factory_entities(
    '{"orgs": [...], "guests": [...], ...}'::jsonb,
    NULL::jsonb
)
```

### 4. Tool Registry Integration

The `ExecuteUpsertTool` is registered in `ToolRegistry._register_default_tools()`:

```python
def _register_default_tools(self):
    self.register(SqlPitbossTool(self.db_pool, self.config))
    self.register(DataTableTool(self.db_pool))
    self.register(RegisterViewTool(self.db_pool))
    self.register(ExecuteUpsertTool(self.db_pool))  # NEW
```

The agent calls it via:

```python
upsert_res = await tool_registry.execute(
    "execute_upsert",
    jsonb_payload=extracted_entities
)
```

## Message Flow Diagram

```
User: "extract https://..."
  ↓
model.LanguageCapo
  ↓ (verb=CONTENT)
model.Capo_content
  ↓ (decision=yes)
model.verifyRequest_content
  ↓ (decision=yes)
model.requestToExtractEntities
  ├─ Fetches URL content
  ├─ Calls EXTRACT_CONTENT LLM prompt
  ├─ Returns extracted_entities in message_body
  └─ decision=no (HITL for human review)
  ↓ (human approves)
model.verifyUpsert
  ├─ Validates extracted_entities structure
  ├─ Checks referential integrity
  ├─ Validates safety constraints
  └─ decision=yes → next: tool.executeSQL
  ↓
tool.executeSQL (CONTENT branch)
  ├─ Detects _verb="CONTENT"
  ├─ Calls ExecuteUpsertTool.execute()
  │  └─ CALL upsert_pattern_factory_entities($1::jsonb, NULL::jsonb)
  ├─ Sets upsert_status="success" in message_body
  └─ decision=yes → terminal (sendMessageToChat)
```

## Error Handling

If validation fails at any stage:

1. **agent_verify_upsert fails** → decision="no" with error reason → HITL (frontend shows error)
2. **ExecuteUpsertTool fails** → Returns `{"status": "error", "error": "..."}` → agent_execute_sql returns decision="no"

## Testing the Flow

### 1. Extract Content
```
User: extract https://example.substack.com/p/my-post
```

### 2. Review Extracted Entities
Frontend displays the extracted JSON for human review.

### 3. Approve (HITL)
Frontend sends back HITL response with `nextAgent: model.verifyUpsert`.

### 4. Validate & Execute
- `verifyUpsert` validates the payload
- `executeSQL` calls the procedure
- Database upserts entities with relationships

## Key Implementation Files

- **backend/pitboss/agents.py**: `agent_verify_upsert`, `agent_execute_sql` (dual-flow)
- **backend/pitboss/tools.py**: `ExecuteUpsertTool` (new)
- **backend/pitboss/supervisor.py**: Passes `_verb` to message_body
- **backend/pitboss/workflow.py**: Routes verifyUpsert → executeSQL (already configured)

## Notes

- The `ExecuteUpsertTool` does not modify the payload—it only calls the procedure. The procedure (`upsert_pattern_factory_entities`) handles all database operations.
- Parameterized queries protect against SQL injection (the payload is converted to JSONB and passed safely).
- The second argument to `CALL` is `NULL::jsonb` because the procedure is designed for bidirectional communication; we only use the input.
