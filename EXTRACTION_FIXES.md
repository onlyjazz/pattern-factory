# Entity Extraction Bug Fixes

## Issues Found

### 1. Duplicate Keys in Response
**Problem**: The JSON response had duplicate keys (e.g., `orgs` appearing both in `messageBody` and at top level)

**Root Cause**: The agent was returning JSON as a STRING in the `reason` field, which was being parsed by the frontend envelope system, creating duplicates.

**Fix**: 
- Return extracted entities in `message_body.extracted_entities` (structured object)
- Return only a human-readable SUMMARY in the `reason` field (string)
- This prevents JSON parsing from duplicating keys

### 2. Missing Patterns and Organizations
**Problem**: The LLM extraction returned empty arrays for patterns and organizations

**Root Cause**: 
- The system prompt from YAML is conservative: "Never hallucinate", "No invented patterns"
- Not enough content was being passed to the LLM (8KB limit)
- Guest extraction was too aggressive (extracting newsletter author instead of mentioned guests)

**Fixes**:
- Increased content passed to LLM from 8KB to 12KB
- Enhanced user message with explicit `Content Source: substack` context
- LLM now has more context to identify real vs. incidental mentions

### 3. Incorrect Guest Extraction
**Problem**: Extracted the newsletter author (Danny Lieberman) instead of the actual guest (Ronen Veksler from Promise Bio)

**Root Cause**: The LLM follows the system prompt which says to extract "identifiable humans" but was prioritizing author byline over guest mentions in content.

**Solution**: 
- System prompt already specifies "Extract identifiable humans (CEOs, founders, researchers, speakers)"
- Passing more content (12KB) helps LLM distinguish between author vs. guests mentioned in content
- The YAML prompt needs refinement (future task) to emphasize: "Guests are people MENTIONED IN the content, not the author"

## Changes Made

### backend/pitboss/agents.py

**Before:**
```python
# Returned JSON string in reason field
reason = json.dumps(extracted_data, ensure_ascii=False, indent=2)
return ("no", 0.95, reason)
```

**After:**
```python
# Store structured data in message_body
message_body["extracted_entities"] = extracted_data

# Return human-readable summary in reason
entity_counts = {
    "posts": len(extracted_data.get("posts", [])),
    "patterns": len(extracted_data.get("patterns", [])),
    "orgs": len(extracted_data.get("orgs", [])),
    "guests": len(extracted_data.get("guests", [])),
}
summary = (
    f"Extracted: {entity_counts['posts']} posts, {entity_counts['patterns']} patterns, "
    f"{entity_counts['orgs']} orgs, {entity_counts['guests']} guests.\n\n"
    f"Extracted data is in message_body.extracted_entities for human review."
)
return ("no", 0.95, summary)
```

Also:
- Increased content size: `8000` → `12000`
- Added content source context: `f"Content Source: substack\n"`
- Improved structure validation: Check `isinstance(extracted_data[key], list)`

## Response Format (After Fix)

```json
{
  "type": "response",
  "verb": "CONTENT",
  "nextAgent": "model.verifyUpsert",
  "decision": "no",
  "confidence": 0.95,
  "reason": "Extracted: 1 posts, 2 patterns, 3 orgs, 4 guests.\n\nExtracted data is in message_body.extracted_entities for human review.",
  "messageBody": {
    "url": "https://...",
    "http_status": 200,
    "content_type": "text/html",
    "extracted_entities": {
      "posts": [...],
      "patterns": [...],
      "orgs": [...],
      "guests": [...],
      "pattern_post_link": [...],
      "pattern_org_link": [...],
      "pattern_guest_link": [...]
    }
  }
}
```

**Key differences:**
- ✅ NO duplicate keys
- ✅ Extracted data is in `.messageBody.extracted_entities`
- ✅ Reason is a simple summary string
- ✅ Clean envelope structure

## Next Steps for Better Extraction

### 1. Improve System Prompt
The YAML EXTRACT_CONTENT prompt needs refinement:
```yaml
GUESTS:
Extract identifiable humans MENTIONED IN THE CONTENT (speakers, founders, researchers).
IMPORTANT: These are people referenced in the article content, NOT the newsletter author.
The author's name appears in bylines but is not a "guest".
Only extract people explicitly mentioned as being interviewed, quoted, or discussed.
```

### 2. Add Content Categorization
Pass hints to LLM about article structure:
- "Author byline section" → ignore
- "Main content section" → extract from here
- "Guest bio section" → extract from here

### 3. Multi-source Support
Different sources (Substack, Beehiiv, Granola, X) have different HTML structures. The agent should:
1. Detect content source from HTML
2. Use source-specific extraction rules
3. Return source-specific metadata

### 4. Entity Deduplication
Before returning, de-duplicate:
- Check if guest is already in database
- Check if org is already in database
- Merge if duplicate (same name/similar description)
- Link to existing entities

## Testing

All tests pass after fixes ✅

```bash
python test_generalized_extraction.py
python test_extract_flow.py
python test_url_extraction_bug.py
```

## Summary

The main fixes were:
1. **Structural**: Stop returning JSON string in reason; use `message_body.extracted_entities` instead
2. **Content**: Increase content passed to LLM from 8KB to 12KB
3. **Context**: Add content source hint to help LLM

These changes eliminate duplicate keys and provide better context for extraction. The guest/pattern/org extraction quality will improve as:
- Users provide feedback during HITL review
- System prompt is refined
- Entity deduplication is added
