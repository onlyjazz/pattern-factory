# Pattern Factory Message Protocol Architecture

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          FRONTEND (Svelte)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ChatInterface.svelte                                              │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ Session ID: sess-abc123                                    │  │
│  │ Request Counter: req-001, req-002, ...                     │  │
│  │                                                             │  │
│  │  User Input → "run Show patterns"                          │  │
│  │                      ↓                                      │  │
│  │  Build MessageEnvelope {                                   │  │
│  │    type: "request",                                        │  │
│  │    verb: "RULE",                                           │  │
│  │    nextAgent: "model.Capo",                                │  │
│  │    messageBody: {rule_text: "..."}
│  │  }                                                          │  │
│  │                      ↓                                      │  │
│  │  WebSocket.send() ──────┐                                  │  │
│  │                          │                                  │  │
│  │  Parse ResponseEnvelope  │                                  │  │
│  │  ↑                        │                                  │  │
│  │  Display:                │                                  │  │
│  │  [YES] (85%)             │                                  │  │
│  │  Reason: Rule syntax valid
│  │  Next: model.verifyRequest                                 │  │
│  └────────────────┬─────────┼─────────────────────────────────┘  │
│                   │         └─────────────────────────────────┐   │
└───────────────────┼─────────────────────────────────────────────┘   
                    │ WebSocket                           │
              ┌─────▼────────────────────────────────────┼─────┐
              │              BACKEND (FastAPI)           │     │
              ├─────────────────────────────────────────────────┤
              │                                                 │
              │  WebSocket Handler (services/api.py)           │
              │  ┌────────────────────────────────────────┐   │
              │  │ Receive JSON message                   │   │
              │  │ if type in ['request', 'response']     │   │
              │  │   → supervisor.process_envelope()     │   │
              │  └──────────┬─────────────────────────────┘   │
              │             │                                   │
              │             ▼                                   │
              │  PitbossSupervisor (supervisor.py)             │
              │  ┌──────────────────────────────────────────┐ │
              │  │ process_envelope(envelope_dict)          │ │
              │  │   ↓                                       │ │
              │  │ WorkflowEngine: Load workflow by verb     │ │
              │  │   ↓                                       │ │
              │  │ FOR each agent in decision tree:          │ │
              │  │   ↓                                       │ │
              │  │   call_agent(agent_name, verb, body)    │ │
              │  │   ← returns (decision, confidence, reason) │
              │  │   ↓                                       │ │
              │  │   Get next_agent from workflow           │ │
              │  │   ↓                                       │ │
              │  │   Send response envelope → WebSocket     │ │
              │  │   ↓                                       │ │
              │  │   IF decision == "no" STOP (HITL)        │ │
              │  │   IF next_agent == terminal STOP         │ │
              │  │   ELSE continue loop                     │ │
              │  └──────────────────────────────────────────┘ │
              │             │                                   │
              │             ▼                                   │
              │  WorkflowEngine (workflow.py)                  │
              │  ┌──────────────────────────────────────────┐ │
              │  │ Workflow Trees (RULE and CONTENT)        │ │
              │  │                                          │ │
              │  │ RULE:                                    │ │
              │  │ model.Capo                               │ │
              │  │   ├─ yes → model.verifyRequest           │ │
              │  │   └─ no  → sendMessageToChat (terminal)  │ │
              │  │ model.verifyRequest                      │ │
              │  │   ├─ yes → model.ruleToSQL               │ │
              │  │   └─ no  → sendMessageToChat             │ │
              │  │ [... more nodes ...]                     │ │
              │  │                                          │ │
              │  │ CONTENT: [similar structure]             │ │
              │  │                                          │ │
              │  │ Methods:                                 │ │
              │  │ - get_workflow(verb) → nodes             │ │
              │  │ - get_next_agent(verb, agent, decision)  │ │
              │  │ - is_terminal(agent) → bool              │ │
              │  └──────────────────────────────────────────┘ │
              │             │                                   │
              │             ▼                                   │
              │  Agents Module (agents.py)                     │
              │  ┌──────────────────────────────────────────┐ │
              │  │ RULE Flow:                               │ │
              │  │ - agent_capo_rule() → (yes|no, conf, r)  │ │
              │  │ - agent_verify_request() → tuple         │ │
              │  │ - agent_rule_to_sql() → tuple            │ │
              │  │ - agent_verify_sql() → tuple             │ │
              │  │ - agent_execute_sql() → tuple            │ │
              │  │                                          │ │
              │  │ CONTENT Flow:                            │ │
              │  │ - agent_capo_content() → tuple           │ │
              │  │ - agent_verify_request_content() → ...   │ │
              │  │ - agent_request_to_extract_entities()    │ │
              │  │ - agent_verify_upsert() → tuple          │ │
              │  │ - agent_execute_sql() → tuple            │ │
              │  │                                          │ │
              │  │ Interface:                               │ │
              │  │ async def agent_X(...) →                 │ │
              │  │   (decision, confidence, reason)         │ │
              │  │                                          │ │
              │  │ Stub: Randomized yes/no + reasons        │ │
              │  │ Real: Call LLMs (model.* agents) &       │ │
              │  │       DB operations (tool.* agents)      │ │
              │  └──────────────────────────────────────────┘ │
              │                                                 │
              └─────────────────────────────────────────────────┘
```

## Message Flow Sequence

### Happy Path (All "Yes" Decisions)

```
┌──────────┐                                              ┌──────────┐
│ Frontend │                                              │ Backend  │
└────┬─────┘                                              └────┬─────┘
     │                                                         │
     │ 1. Request MessageEnvelope                              │
     │    type: "request", verb: "RULE",                     │
     │    nextAgent: "model.Capo"                            │
     ├────────────────────────────────────────────────────────▶
     │                                                         │ 2. Process
     │                                                         │    envelope
     │                                                         │
     │                                      3. Response 1     │
     │                                         [model.Capo]    │
     │    decision: "yes" (0.85)                │             │
     │    nextAgent: "model.verifyRequest"      │             │
     │◀─────────────────────────────────────────┼─────────────┤
     │ Display: [YES] (85%) → Rule syntax valid              │
     │         Next: model.verifyRequest                     │
     │                                                         │
     │                                      4. Response 2     │
     │                                      [model.verify...]  │
     │    decision: "yes" (0.88)                │             │
     │    nextAgent: "model.ruleToSQL"         │             │
     │◀─────────────────────────────────────────┼─────────────┤
     │ Display: [YES] (88%) → Semantics clear                │
     │         Next: model.ruleToSQL                         │
     │                                                         │
     │                                      5. Response 3     │
     │                                      [model.ruleToSQL]  │
     │    decision: "yes" (0.92)                │             │
     │    nextAgent: "model.verifySQL"         │             │
     │◀─────────────────────────────────────────┼─────────────┤
     │ Display: [YES] (92%) → SQL generated                   │
     │         Next: model.verifySQL                         │
     │                                                         │
     │    [... more responses ...]                            │
     │                                                         │
     │                                      N. Final Response  │
     │                                      [tool.executeSQL]  │
     │    decision: "yes" (0.96)                │             │
     │    nextAgent: null                      │             │
     │    returnCode: 1                        │             │
     │◀─────────────────────────────────────────┼─────────────┤
     │ Display: ✅ SUCCESS (96%)                             │
     │         42 rows materialized                          │
     │                                                         │
```

### HITL Path ("No" Decision)

```
┌──────────┐                                              ┌──────────┐
│ Frontend │                                              │ Backend  │
└────┬─────┘                                              └────┬─────┘
     │                                                         │
     │ 1. Request MessageEnvelope                              │
     │    type: "request", verb: "RULE",                     │
     │    nextAgent: "model.Capo"                            │
     ├────────────────────────────────────────────────────────▶
     │                                                         │
     │                                      2. Response 1     │
     │                                         [model.Capo]    │
     │    decision: "yes" (0.85)                │             │
     │    nextAgent: "model.verifyRequest"      │             │
     │◀─────────────────────────────────────────┼─────────────┤
     │ Display: [YES] (85%)                                   │
     │                                                         │
     │                                      3. Response 2     │
     │                                      [model.verify...]  │
     │    decision: "NO" (0.44)  ◀─── HITL!    │             │
     │    nextAgent: "sendMessageToChat"       │             │
     │    reason: "Cannot determine entity"    │             │
     │◀─────────────────────────────────────────┼─────────────┤
     │ Display: ❌ NO (44%)                                   │
     │         Cannot determine entity types                 │
     │         Next: sendMessageToChat                       │
     │                                                         │
     │ ⚠️  WORKFLOW STOPPED - AWAITING HUMAN INPUT            │
     │                                                         │
     │ User reviews and corrects...                           │
     │ User sends: "Yes, it should be pattern"                │
     │                                                         │
     │ (Future: Send approval envelope to continue)           │
     │                                                         │
```

## Component Interactions

### Envelope ↔ Frontend

```
Frontend creates request:
  makeRequest(sessionId, requestId, verb, body)
  → MessageEnvelope(type="request", ...)
  → JSON string
  → WebSocket.send()

Backend creates response:
  make_response(sessionId, requestId, verb, 
                nextAgent, decision, confidence, reason, body)
  → MessageEnvelope(type="response", ...)
  → .to_dict()
  → JSON
  → WebSocket.send_json()

Frontend receives:
  WebSocket.onmessage(event)
  → JSON.parse(event.data)
  → ParseEnvelope(data) or direct access (both work)
  → Read: decision, confidence, reason, nextAgent
```

### Supervisor ↔ Workflow ↔ Agents

```
Supervisor.process_envelope():
  1. Parse MessageEnvelope from dict
  2. Extract verb (RULE or CONTENT)
  3. Get current_agent from envelope.nextAgent or "model.Capo"
  4. Loop until terminal or HITL:
     a. Call agent:
        decision, conf, reason = await call_agent(
          current_agent, verb, messageBody
        )
     b. Get next via workflow:
        next_agent = workflow.get_next_agent(
          verb, current_agent, decision
        )
     c. Send response envelope
     d. Check for HITL (decision=="no") → Stop
     e. Check for terminal (next_agent==None) → Stop
     f. Set current_agent = next_agent, continue
```

## State Management

### Per Session
- `session_id`: Unique identifier (UUID-like)
- `messages[]`: All messages in conversation (frontend)
- `workflow_history[]`: All agent decisions (backend, future)

### Per Request
- `request_id`: Unique within session (req-001, req-002, ...)
- `timestamp`: When request started
- `verb`: RULE or CONTENT (immutable after request)
- `messageBody`: Original request data

### Per Agent Step
- `nextAgent`: Current agent being executed
- `decision`: "yes" or "no" (agent's choice)
- `confidence`: 0.0-1.0 (agent's certainty)
- `reason`: Human-readable explanation
- `returnCode`: 0 (continue), 1 (success), -1 (error)

## Future Enhancements

### YAML Workflow Loading
```yaml
# workflows.yaml
WORKFLOWS:
  RULE:
    model.Capo:
      yes: model.verifyRequest
      no: sendMessageToChat
      description: "Initial validation"
    model.verifyRequest:
      yes: model.ruleToSQL
      no: sendMessageToChat
      description: "Semantic validation"
    # ...
```

### Agent Registry with Metadata
```python
AGENT_REGISTRY = {
    "model.Capo": {
        "function": agent_capo,
        "timeout": 5.0,
        "retryable": True,
        "description": "Initial validation"
    },
    # ...
}
```

### Workflow Execution History
```python
# Store in system_log
{
  "request_id": "req-001",
  "session_id": "sess-abc",
  "timestamp": 1732535853442,
  "steps": [
    {"agent": "model.Capo", "decision": "yes", "confidence": 0.85},
    {"agent": "model.verifyRequest", "decision": "no", "confidence": 0.44},
  ],
  "hitl_triggered": True,
  "hitl_approved_by": "user@example.com",
  "final_status": "approved"
}
```

### HITL Response Continuation
```json
{
  "type": "response",
  "request_id": "req-001",
  "hitl_response": {
    "approved": true,
    "corrections": {"rule_text": "Show me patterns"},
    "approved_by": "user@example.com",
    "timestamp": 1732535900000
  }
}
```
