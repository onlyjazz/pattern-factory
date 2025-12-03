# Final Fix: Capo Validation & No Duplicate Messages

## Two Issues Fixed

### Issue 1: Capo's Job
**Old**: Capo tried to validate rule_logic and rule_code (which don't exist yet when user types "run KUKU")
**New**: Capo validates the message envelope - checks if raw_text is present

```python
# agents.py - agent_capo_rule
async def agent_capo_rule(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """model.Capo (RULE flow entry point) - validates message envelope"""
    raw_text = message_body.get("raw_text", "").strip()
    
    if not raw_text:
        return ("no", 1.0, "Message is empty. Please type something.")
    
    return ("yes", 1.0, "Message envelope is valid and ready for processing")
```

Flow when user types "run KUKU":
1. Frontend sends envelope with raw_text="run KUKU"
2. supervisor validates envelope verb (already done at entry)
3. supervisor calls LanguageCapo → returns verb="RULE"
4. supervisor enters RULE workflow
5. supervisor calls model.Capo
6. ✅ Capo validates raw_text exists → returns YES
7. supervisor continues to model.verifyRequest
8. ✅ verifyRequest checks if "KUKU" exists in YAML → returns NO with error message
9. ✅ Frontend shows: "Rule 'KUKU' not found in YAML..."
10. ✅ No crash, response sent once

### Issue 2: Duplicate Messages
**Old**: Two send_json calls - one at line 201 (step_resp) and one at line 217 (rejection_resp)
**New**: Single send_json call with return_code set appropriately

```python
# supervisor.py - single response send
return_code = -1 if dec_enum == Decision.NO else 0
next_agent_target = next_agent if dec_enum == Decision.YES else "sendMessageToChat"

step_resp = make_response(
    ...
    next_agent=next_agent_target,
    return_code=return_code,
)
await self._send_envelope(step_resp)  # Send once

if dec_enum == Decision.NO:
    return  # Exit, don't send again
```

## Key Changes

### agents.py (lines 249-276)
- Capo now validates envelope structure only
- Checks if raw_text is present (message is not empty)
- No longer checks rule_logic or rule_code

### supervisor.py (lines 179-207)  
- Single response send at line 203 instead of two sends
- return_code = -1 when decision is NO, 0 when decision is YES
- next_agent points to "sendMessageToChat" when decision is NO
- No duplicate rejection_resp send

## Result
✅ No more crashes on invalid verbs
✅ No more duplicate messages
✅ User gets one clear error message per invalid input
✅ Proper separation of concerns - Capo routes, verifyRequest validates
