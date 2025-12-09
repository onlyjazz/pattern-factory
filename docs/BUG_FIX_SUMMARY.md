# Bug Fix: Backend Crash on Invalid Rule Execution

## Problem Statement

When a user clicks to run a non-existent rule (e.g., "run NONEXISTENT_RULE"), the backend crashes with:

```
ValueError: '' is not a valid Verb
INFO:     connection closed
```

This crash violates the separation of concerns principle—the **verify request stage** should catch validation errors and return a user-friendly error message instead of crashing.

## Root Causes

### 1. **Unvalidated Enum Deserialization** (`envelope.py`)
   - `MessageEnvelope.from_dict()` attempts to construct Verb enum from user-supplied strings without validation
   - If `verb` field is empty or invalid, `Verb("")` raises `ValueError` 
   - This crashes the entire WebSocket connection

### 2. **Unsafe Error Recovery** (`supervisor.py`)
   - When `from_dict()` fails, the error handler tries: `Verb(envelope_dict.get("verb", "RULE"))`
   - If the original verb was an empty string, this also crashes

### 3. **Missing Rule Existence Check** (`agents.py`)
   - `agent_verify_request()` validates rule logic syntax but **doesn't verify the rule_code exists in YAML**
   - Invalid rule codes pass through early validation stages
   - Crash occurs downstream when agents attempt to process a non-existent rule

## Solutions Implemented

### 1. **Enhanced Enum Validation** (`envelope.py`, lines 97-105)
```python
if isinstance(data.get("verb"), str):
    verb_str = data["verb"].strip() if data["verb"] else ""
    if not verb_str:
        raise ValueError("Verb field is empty or missing")
    try:
        data["verb"] = Verb(verb_str)
    except ValueError:
        available_verbs = ", ".join([v.value for v in Verb])
        raise ValueError(f"Invalid verb: '{verb_str}'. Available: {available_verbs}")
```
- **Validates before constructing enum**
- **Strips whitespace** to handle edge cases
- **Provides helpful error message** listing available verbs

### 2. **Safe Error Recovery** (`supervisor.py`, lines 73-84)
```python
verb_str = envelope_dict.get("verb", "").strip() if isinstance(envelope_dict.get("verb"), str) else ""
safe_verb = Verb.GENERIC if not verb_str or verb_str not in [v.value for v in Verb] else Verb(verb_str)
```
- **Type-checks before accessing verb string**
- **Falls back to `Verb.GENERIC`** for invalid/missing verbs
- **Never crashes during error recovery** (prevents double-crash)

### 3. **Rule Existence Validation** (`agents.py`, lines 301-310)
```python
if rule_code:
    context_builder = message_body.get("_ctx")
    if context_builder and hasattr(context_builder, 'yaml_data'):
        rules = context_builder.yaml_data.get("RULES", [])
        rule_codes = [r.get("rule_code") for r in rules]
        
        if rule_code not in rule_codes:
            reason = f"Rule '{rule_code}' not found in YAML. Available rules: {', '.join(rule_codes[:5])}"
            logger.info(f"  Decision: no (confidence: 0.98) - {reason}")
            return ("no", 0.98, reason)
```
- **Early validation** in `agent_verify_request()` (before SQL generation)
- **Lists available rules** to help users correct typos
- **Returns user-friendly error message** instead of crashing

### 4. **Explicit Error Response** (`supervisor.py`, lines 192-205)
```python
if dec_enum == Decision.NO:
    rejection_resp = make_response(
        session_id=env.session_id,
        request_id=env.request_id,
        verb=env.verb,
        next_agent="sendMessageToChat",
        decision=dec_enum,
        confidence=float(confidence),
        reason=str(reason),
        message_body=frontend_body,
        return_code=-1,
    )
    await self._send_envelope(rejection_resp)
    return
```
- **Sends proper rejection response** when verification fails
- **Marks response with `return_code=-1`** to signal error to frontend
- **Frontend can now display user-friendly message** instead of showing crash

## Testing Recommendations

1. **Test Invalid Rule Code**
   ```
   Send: {"type": "request", "verb": "RULE", "messageBody": {"raw_text": "run INVALID_RULE"}}
   Expected: Error response with "Rule 'INVALID_RULE' not found in YAML. Available rules: ..."
   ```

2. **Test Empty Verb**
   ```
   Send: {"type": "request", "verb": "", "messageBody": {...}}
   Expected: Error response about invalid verb, NOT a crash
   ```

3. **Test Missing Verb Field**
   ```
   Send: {"type": "request", "messageBody": {...}}
   Expected: MessageEnvelope defaults to verb=RULE, processing continues normally
   ```

4. **Test Valid Rule**
   ```
   Send: {"type": "request", "verb": "RULE", "messageBody": {"raw_text": "run LIST_PATTERNS"}}
   Expected: Normal processing flow continues
   ```

## Architecture Improvements

This fix demonstrates proper **separation of concerns**:
- **Envelope layer** validates protocol format (enums, types)
- **Agent layer** validates business logic (rule existence, entity references)
- **Error recovery** gracefully degrades instead of crashing
- **Frontend receives actionable error messages** instead of WebSocket disconnects

## Files Modified

- `backend/pitboss/envelope.py` (lines 87-117): Enhanced enum validation in `from_dict()`
- `backend/pitboss/supervisor.py` (lines 57-84, 192-205): Safe error recovery and explicit rejection responses
- `backend/pitboss/agents.py` (lines 284-310): Rule existence check in `agent_verify_request()`
