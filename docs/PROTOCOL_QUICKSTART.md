# Message Protocol v1.1 Quick Start

## For Frontend Developers

### Sending a Request

```typescript
import { makeRequest } from '$lib/types/envelope';

const request = makeRequest(
  sessionId,    // auto-generated string
  requestId,    // auto-incremented per session
  'RULE',       // verb: 'RULE' | 'CONTENT'
  {
    rule_text: 'Show me patterns in episodes'
  }
);

websocket.send(JSON.stringify(request));
```

### Receiving a Response

```typescript
websocket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  // Check for envelope response
  if (data.type === 'response' || data.type === 'error') {
    const envelope = data; // Already valid MessageEnvelope
    
    console.log(`Agent decision: ${envelope.decision}`);
    console.log(`Confidence: ${(envelope.confidence * 100).toFixed(0)}%`);
    console.log(`Reason: ${envelope.reason}`);
    console.log(`Next agent: ${envelope.nextAgent}`);
    
    // HITL check
    if (envelope.decision === 'no') {
      // Stop processing, wait for user input
      console.log('Requires human approval');
    }
  }
};
```

## For Backend Developers

### Creating Responses in Python

```python
from pitboss.envelope import make_response, Decision, Verb

# Agent returns decision
response = make_response(
    session_id="sess-001",
    request_id="req-001",
    verb=Verb.RULE,
    next_agent="model.verifyRequest",
    decision=Decision.YES,
    confidence=0.85,
    reason="Rule syntax appears valid",
    message_body={"rule_text": "..."},
)

await websocket.send_json(response.to_dict())
```

### Implementing an Agent

```python
from pitboss.agents import call_agent

async def agent_my_validator(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """Custom agent implementation."""
    
    # Do validation logic
    is_valid = validate_something(message_body)
    
    # Return decision tuple
    if is_valid:
        return (
            "yes",      # decision
            0.92,       # confidence (0.0-1.0)
            "Validation passed"  # reason
        )
    else:
        return (
            "no",
            0.65,
            "Validation failed: missing required fields"
        )
```

### Workflow Navigation

```python
from pitboss.workflow import WorkflowEngine

engine = WorkflowEngine()

# Get next agent based on decision
next_agent = engine.get_next_agent(
    verb="RULE",
    current_agent="model.Capo",
    decision="yes"
)
# Returns: "model.verifyRequest"

# Check if terminal
if engine.is_terminal(next_agent):
    print("Workflow complete")
```

## Message Flow Examples

### Happy Path (RULE Flow - All Yes)

```
User: "run Show patterns in episodes"
  ↓ 
Frontend sends: {type: "request", verb: "RULE", nextAgent: "model.Capo", ...}
  ↓
Backend [model.Capo]:        YES (0.85) → "Rule syntax valid"
  ↓ (yes branch)
Backend [model.verifyRequest]: YES (0.88) → "Semantics clear"
  ↓ (yes branch)
Backend [model.ruleToSQL]:    YES (0.92) → "SQL generated"
  ↓ (yes branch)
Backend [model.verifySQL]:    YES (0.97) → "SQL safe"
  ↓ (yes branch)
Backend [tool.executeSQL]:    YES (0.96) → "42 rows materialized"
  ↓ (yes branch, terminal)
Frontend displays: ✅ Success! 42 rows
```

### HITL Path (No Decision)

```
User: "run Ambiguous rule request"
  ↓
Frontend sends: {type: "request", verb: "RULE", nextAgent: "model.Capo", ...}
  ↓
Backend [model.Capo]:        YES (0.85) → "Proceeding..."
  ↓ (yes branch)
Backend [model.verifyRequest]: NO (0.44) → "Cannot determine entity types"
  ↓ (no branch → sendMessageToChat)
Frontend displays: 
  ❌ NO (44%)
  Cannot determine entity types
  Next: sendMessageToChat
  
  [Waiting for human input]
```

## Envelope Fields Explained

| Field | Type | Example | Purpose |
|-------|------|---------|----------|
| `type` | "request" \| "response" \| "error" | "response" | Message category |
| `version` | string | "1.1" | Protocol version for forward compatibility |
| `timestamp` | number | 1732535853442 | Milliseconds since epoch |
| `session_id` | string | "sess-abc123" | Session identifier (groups related requests) |
| `request_id` | string | "req-001" | Unique request ID (for tracing) |
| `verb` | "RULE" \| "CONTENT" | "RULE" | What type of operation |
| `nextAgent` | string \| null | "model.verifyRequest" | Next agent in workflow |
| `returnCode` | number | 0 \| 1 \| -1 | 0=continue, 1=success, -1=error |
| `decision` | "yes" \| "no" \| null | "yes" | Agent's decision for branching |
| `confidence` | number | 0.85 | Agent confidence 0.0-1.0 |
| `reason` | string | "Rule syntax valid" | Why agent decided yes/no |
| `messageBody` | object | {"rule_text": "..."} | Verb-specific data |

## Common Workflows

### Adding a New Agent

1. Create function in `backend/pitboss/agents.py`:
   ```python
   async def agent_my_new_agent(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
       # implementation
       return ("yes", 0.90, "reason")
   ```

2. Add to `call_agent()` dispatcher:
   ```python
   elif agent_name == "my.newAgent":
       agent_fn = agent_my_new_agent
   ```

3. Define workflow path in `WorkflowEngine._load_workflows()`:
   ```python
   "my.newAgent": WorkflowNode(
       agent_name="my.newAgent",
       branch_yes="next.agent",
       branch_no="sendMessageToChat"
   ),
   ```

### Adding a New Workflow Verb

1. Update `backend/pitboss/workflow.py` in `_load_workflows()`:
   ```python
   self.workflows["NEWVERB"] = {
       "model.Capo": WorkflowNode(...),
       # ... define path
   }
   ```

2. Update `src/lib/types/envelope.ts` type:
   ```typescript
   export type Verb = 'RULE' | 'CONTENT' | 'NEWVERB';
   ```

3. Frontend can now send:
   ```typescript
   makeRequest(sessionId, requestId, 'NEWVERB', messageBody)
   ```

## Testing

Run the comprehensive test suite:
```bash
cd backend
python test_message_protocol.py
```

This tests:
- Envelope serialization/deserialization
- Workflow tree navigation
- Agent decision execution
- Complete workflow walkthrough
- Response message generation

## Debugging

### Check logs
```bash
# Backend logs show agent decisions
🤖 [model.Capo] Validating rule request...
  Decision: yes (confidence: 0.85)
🔄 Workflow branching: model.Capo (yes) → model.verifyRequest
```

### Debug a specific agent
```python
from pitboss.agents import call_agent
import asyncio

async def debug():
    decision, conf, reason = await call_agent("model.Capo", "RULE", {})
    print(f"Decision: {decision}, Confidence: {conf}, Reason: {reason}")

asyncio.run(debug())
```

### Trace a request through frontend
1. Open browser DevTools → Console
2. Send message starting with "run "
3. Look for envelope logs:
   ```
   Sending envelope: {type: "request", version: "1.1", ...}
   ```
4. Responses logged as:
   ```
   [YES] (85%)
   Rule syntax appears valid
   Next: model.verifyRequest
   ```

## Next: Real Agent Implementation

Stub agents currently return random decisions. To implement real logic:

1. Replace `agent_rule_to_sql()` with LLM call:
   ```python
   async def agent_rule_to_sql(message_body):
       rule_text = message_body.get("rule_text")
       
       # Call GPT-4o to generate SQL
       from pitboss.context_builder import ContextBuilder
       context = ContextBuilder(db).build_context(rule_code=rule_text)
       
       # LLM logic here...
       
       if sql_valid:
           return ("yes", 0.92, f"Generated: {sql[:50]}...")
       else:
           return ("no", 0.55, "Could not generate valid SQL")
   ```

2. Similar for other agents in the pipeline

3. Keep decision/confidence/reason tuple interface for consistency
