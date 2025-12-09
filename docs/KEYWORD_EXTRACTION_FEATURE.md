# LLM-Powered Keyword Extraction Feature

## What's New
Extended `model.requestToExtractEntities` to return a structured JSON object with:
- **Post metadata**: name (title), description (subtitle)
- **Keywords**: 3-10 relevant keywords extracted via OpenAI LLM
- **Publication info**: content_source="substack", published_at date
- **URL**: Original content_url for database linkage

## JSON Output Structure

The agent now returns this in the `reason` field (for HITL review):

```json
{
  "name": "Post Title Here",
  "description": "Post Subtitle or Description",
  "keywords": [
    "keyword1",
    "keyword2",
    "keyword3",
    ...
  ],
  "content_url": "https://substack.com/original-url",
  "content_source": "substack",
  "published_at": "Oct 24, 2025"
}
```

## Keyword Extraction Strategy

### Primary: OpenAI LLM (gpt-4o-mini)
- Called asynchronously with temperature=0.2 (deterministic)
- Input: title + subtitle + first 4KB of content preview
- Output: JSON with "keywords" array (3-10 items)
- Timeout: 10 seconds
- Returns normalized list (lowercase, deduplicated)

### Fallback: Heuristic Extraction
- Triggered if:
  - OPENAI_API_KEY not set
  - LLM request fails
  - JSON parsing fails
- Algorithm:
  - Extract words from title + subtitle (3+ chars)
  - Remove common stopwords (the, and, for, etc.)
  - Deduplicate and limit to 10 items
  - Return lowercase list

## Usage in the Flow

1. User types: `extract https://substack.com/post-slug`
2. Agent fetches HTML, extracts title/subtitle/date
3. Agent calls OpenAI to extract keywords
4. Agent builds JSON object
5. Agent returns `decision=no` with JSON in reason field
6. Frontend displays JSON for human review
7. Human approves → continues to model.verifyUpsert (future agent)

## Database Integration (Future)

Once HITL approves, the JSON will be mapped to:
- **posts.name** ← "name" field
- **posts.description** ← "description" field
- **posts.keywords** ← "keywords" array (serialized)
- **posts.url** ← "content_url" field
- **posts.source** ← "content_source" field (always "substack" for now)
- **posts.published_at** ← "published_at" field

## Test Coverage

### test_extract_flow.py
- ✅ Title/subtitle/date parsing from HTML
- ✅ Heuristic keyword generation
- ✅ Full extract flow with valid URL
- ✅ Graceful handling of missing URL
- ✅ Graceful handling of invalid URL

### test_json_output.py
- ✅ Complete JSON structure validation
- ✅ All required fields present
- ✅ Correct content_source hardcoded to "substack"

## Example Output

Running the test:
```bash
python test_json_output.py
```

Shows:
```json
{
  "name": "The Great Brain Bet: How Human-derived mini-brains and AI could upend big pharma",
  "description": "Choosing powers in early stage TechBio",
  "keywords": [
    "great",
    "brain",
    "bet",
    "human-derived",
    "mini-brains",
    "upend",
    "pharma",
    "choosing",
    "powers",
    "techbio"
  ],
  "content_url": "https://substack.com/article",
  "content_source": "substack",
  "published_at": "Oct 24, 2025"
}
```

## Implementation Notes

- Uses only stdlib imports (no new dependencies)
- HTTP fetch runs in background thread (non-blocking)
- Supports multiple date formats (regex flexible)
- Handles missing LLM gracefully (fallback to heuristic)
- Normalizes keywords: lowercase, deduplicated, max 10 items
- All fields stored in message_body for downstream agents

## Next Steps

1. Frontend: Display JSON in HITL panel for human review
2. Frontend: Allow user to edit/approve JSON
3. Backend: Implement model.verifyUpsert to validate upserts
4. Backend: Implement tool.executeSQL to insert into posts table
5. Consider: Multi-source content types beyond Substack
