# Simple Bug Fix: No More Crashes on Invalid Verb

## The Problem
When user types "RUN KUKU" (non-existent rule), the backend crashed with:
```
ValueError: '' is not a valid Verb
```

## Why It Crashed
1. User types "RUN KUKU"
2. LanguageCapo routes it to RULE workflow (correct)
3. But at some point, `Verb("")` or `Verb("invalid")` was called
4. Python enum crashes with ValueError

## The Solution
**Simple rule: NEVER call `Verb(something)` without validating `something` first.**

### Changes Made

**1. supervisor.py (lines 63-91): Validate verb on entry**
```python
verb_str = (envelope_dict.get("verb") or "").strip().upper()

if not verb_str:
    # Return error to frontend, never crash
    return error message
    
if verb_str not in [v.value for v in Verb]:
    # Return error to frontend, never crash
    return error message
```

**2. supervisor.py (lines 129-141): Validate verb from LanguageCapo**
```python
verb_determined = (verb_determined or "").strip().upper()
if verb_determined not in [v.value for v in Verb]:
    # Return error to frontend, never crash
    return error message
    
verb_str = verb_determined  # Safe now
```

**3. agents.py (lines 81-87): LanguageCapo just routes, never validates**
```python
if text.upper().startswith("RUN "):
    code = text[4:].strip()
    reason = f"User wants to run rule: '{code}'"
    return ("yes", 0.95, reason, "RULE")  # Just route, don't verify rule exists
```

**4. agents.py (lines 107-111): LLM verb response validation**
```python
verb = (data.get("verb", "") or "").strip().upper()
if verb not in ("RULE", "CONTENT"):
    verb = "RULE"  # Default to RULE, never empty
```

## Flow When User Types "RUN KUKU"

1. Frontend sends: `{"verb": "GENERIC", "messageBody": {"raw_text": "RUN KUKU"}}`
2. ✅ supervisor validates verb="GENERIC" is valid
3. ✅ Calls LanguageCapo
4. ✅ LanguageCapo sees "RUN " prefix → returns verb="RULE"
5. ✅ supervisor validates verb="RULE" is valid
6. ✅ Routes to model.Capo in RULE workflow
7. ✅ model.Capo enters, processes message
8. ✅ model.verifyRequest checks if "KUKU" exists in YAML
9. ✅ Returns "no" decision with message: "Rule 'KUKU' not found"
10. ✅ Frontend shows user-friendly error message
11. ✅ **No crash, no WebSocket disconnect**

## Key Principle
- **Never construct a Verb enum without validating the string first**
- **If verb is invalid, return error message to frontend, never crash**
- **Each agent has one job - Capo routes, verifyRequest validates rules**
