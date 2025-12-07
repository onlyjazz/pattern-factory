# Extract Content Flow Implementation

## Overview
Implemented the CONTENT workflow starting with `model.requestToExtractEntities` to extract and structure post metadata from URLs (e.g., Substack posts).

The agent fetches HTML, extracts title/subtitle/date, uses OpenAI (with heuristic fallback) to generate keywords, and returns a structured JSON object for human review.

## User Interaction Flow

```
User types: "extract https://example.com/post"
     ↓
[model.Capo]
  ├─ Recognizes \"extract <url>\" syntax
  └─ Returns: decision=yes (confidence 0.99)
     ↓
[model.verifyRequest]
  ├─ Verifies URL is present
  └─ Returns: decision=yes (confidence 0.96)
     ↓
[model.requestToExtractEntities]
  ├─ Performs HTTP GET to fetch URL content
  ├─ Extracts: title, subtitle, published_at from HTML
  ├─ Generates keywords via OpenAI (or heuristic fallback)
  ├─ Builds JSON content_summary
  ├─ Stores metadata in message_body
  └─ Returns: decision=no with JSON in reason (HITL for human review)
```

## Implementation Details

### 1. **URL Parsing Helper** (`_parse_url_from_text`)
- Extracts URL from "extract <url>" pattern
- Returns URL or None if pattern doesn't match

### 2. **HTTP Fetch Helper** (`_http_get_text`)
- Uses stdlib `urllib` (no external HTTP lib dependency)
- Runs in background thread via `asyncio.to_thread()`
- Handles charsets from Content-Type header
- Caps response to 512KB for preview stage
- Returns tuple: `(text, status_code, content_type)`

### 2a. **HTML Parsers**
- `_extract_post_title_and_subtitle(html)`: Regex-based extraction from h1/h3 with class matching
- `_extract_published_date(html)`: Regex patterns to find dates like "Oct 24, 2025" in meta divs
- `_heuristic_keywords(title, desc)`: Simple keyword extraction with stopword filtering (fallback)

### 2b. **LLM Keyword Extraction**
- `_extract_keywords_via_llm()`: Async call to OpenAI (gpt-4o-mini) to extract 3-10 keywords
- Passes title + subtitle + content preview to LLM
- Temperature=0.2 for deterministic extraction
- Falls back to heuristic if OPENAI_API_KEY not set or request fails
- Returns normalized list (lowercase, deduplicated, max 10 items)

### 3. **Agent: model.Capo (CONTENT flow)**
**Purpose**: Initial validation
- Fast-path: recognizes \"extract \" prefix → returns `yes`
- Fallback behavior if not recognized
- **Key change**: Deterministic (no random) for \"extract\" commands

### 4. **Agent: model.verifyRequest (CONTENT flow)**
**Purpose**: Semantic validation
- Checks if URL is present in message_body or raw_text
- If URL found → returns `yes`
- If no URL → returns `no` with usage hint (HITL)
- **Key change**: Deterministic URL lookup, uses `_parse_url_from_text` helper

### 5. **Agent: model.requestToExtractEntities (CONTENT flow)**
**Purpose**: Extract post metadata and return structured JSON for HITL review

**Steps**:
1. Extract URL from raw_text if not already in message_body
2. Validate URL format (http/https scheme and netloc)
3. HTTP Fetch with charset handling and 512KB cap
4. **Parse HTML** using regex to extract:
   - Title from: `<h1 ... class="post-title ...">...</h1>`
   - Subtitle from: `<h3 ... class="subtitle ...">...</h3>`
   - Published date from: `<div ... class="*meta/publish/date*">MMM DD, YYYY</div>` (or any date pattern)
5. **Generate Keywords** (up to 10):
   - Primary: OpenAI LLM (gpt-4o-mini, temperature 0.2)
   - Fallback: Simple heuristic (stop-word removal, dedup)
6. **Build JSON content_summary**:
   ```json
   {
     "name": "post title (title)",
     "description": "post subtitle",
     "keywords": ["keyword1", "keyword2", ...],
     "content_url": "https://original-url",
     "content_source": "substack",
     "published_at": "Oct 24, 2025"
   }
   ```
7. **Stores in message_body**:
   - `post_title`, `post_subtitle`, `published_at`
   - `content_summary`: complete JSON object
   - `url`, `http_status`, `content_type`, `content_preview` (from HTTP fetch)
8. **Returns**: `decision=no` with JSON in reason (HITL for human review)

## Key Features

✅ **Deterministic for 'extract' commands**: No random branching—flow always reaches `requestToExtractEntities`

✅ **HTTP fetch in background thread**: Non-blocking async I/O using stdlib only (no external deps)

✅ **Structured JSON output**: Returns complete metadata object ready for database upsert

✅ **LLM-powered keywords**: Uses OpenAI (with heuristic fallback) to generate relevant 3-10 keywords

✅ **HITL-ready**: Returns `decision=no` with JSON in reason field for human review/approval

✅ **Date extraction**: Parses Substack-style publication dates (e.g., "Oct 24, 2025")

✅ **Error handling**: Gracefully handles invalid URLs, HTTP errors, charset issues, missing LLM keys

## Testing

### Unit Tests
Run `python test_extract_flow.py` to validate:
- ✅ Title/subtitle/date extraction from HTML
- ✅ Heuristic keyword generation
- ✅ Extract flow with valid URL
- ✅ Extract flow without URL
- ✅ Extract with invalid URL

Run `python test_json_output.py` to see the complete JSON structure output for HITL.

## Message Body State After Extraction

```python
message_body = {
    "raw_text": "extract https://substack.com/article",
    "url": "https://substack.com/article",
    "http_status": 200,
    "content_type": "text/html; charset=utf-8",
    "content_preview": "<!doctype html>...",
    "post_title": "The Great Brain Bet: How Human-derived mini-brains and AI could upend big pharma",
    "post_subtitle": "Choosing powers in early stage TechBio",
    "published_at": "Oct 24, 2025",
    "content_summary": {
        "name": "The Great Brain Bet: How Human-derived mini-brains and AI could upend big pharma",
        "description": "Choosing powers in early stage TechBio",
        "keywords": ["automation", "labs", "ai", "biotech", "..."],
        "content_url": "https://substack.com/article",
        "content_source": "substack",
        "published_at": "Oct 24, 2025"
    }
}
```

The `content_summary` JSON is sent to the frontend as the reason field in the NO response.

## Next Steps (Future Agents)

- **model.verifyUpsert**: (Already in workflow) Will verify extracted entities before inserting
- **tool.executeSQL**: Execute upserts to database
- Full LLM-based extraction pipeline (model.extractEntities) to parse entities from fetched content

## Files Modified / Created

**backend/pitboss/agents.py**:
- Added imports: `re` (regex), `urllib.request`
- Added helpers:
  - `_extract_post_title_and_subtitle()`: Extract from h1/h3 tags
  - `_extract_published_date()`: Extract dates like "Oct 24, 2025"
  - `_heuristic_keywords()`: Fallback keyword extraction
  - `_extract_keywords_via_llm()`: OpenAI-powered keyword extraction
- Updated agents:
  - `agent_capo_content()`: Deterministic recognition of 'extract' command
  - `agent_verify_request_content()`: Validate URL presence
  - `agent_request_to_extract_entities()`: Full metadata extraction with JSON output

**test_extract_flow.py** (updated):
- Added title/subtitle/date extraction tests
- Added keywords test
- Enhanced output to show content_summary JSON structure
- Validates JSON structure has all required fields

**test_json_output.py** (new):
- Standalone test demonstrating JSON output for human review
- Shows exactly what HITL user will see in the reason field

## Testing Commands

```bash
# Full extract flow tests
cd /Users/dl/code/pattern-factory
python test_extract_flow.py

# JSON output demonstration
python test_json_output.py
```
