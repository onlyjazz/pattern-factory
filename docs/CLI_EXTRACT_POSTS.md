# Extract Posts CLI Tool

Command-line interface for extracting entities from web content and upserting them to the Pattern Factory database.

## Quick Start

```bash
# Basic usage
./bin/extract-posts https://example.substack.com/p/post-title

# Validate without upserting
./bin/extract-posts https://example.substack.com/p/post-title --dry-run

# Get JSON output
./bin/extract-posts https://example.substack.com/p/post-title --json

# Enable debug logging
./bin/extract-posts https://example.substack.com/p/post-title --verbose
```

## Prerequisites

1. **Environment Variables** (from `.env`):
   - `DATABASE_URL`: PostgreSQL connection string
   - `OPENAI_API_KEY`: OpenAI API key for LLM extraction

2. **Python Dependencies**:
   - asyncpg
   - openai
   - pyyaml
   - (standard from backend/requirements.txt)

## Usage

```
extract-posts <url> [OPTIONS]

Options:
  --dry-run          Validate extraction without upserting to database
  --json             Output raw JSON instead of summary
  --verbose, -v      Enable debug logging
  --help, -h         Show help message
```

## Examples

### Extract and upsert
```bash
./bin/extract-posts https://example.substack.com/p/the-great-brain-bet
```

Output:
```
✅ Success!

📰 Post: 'The Great Brain Bet: How Human-derived mini-brains...' (Oct 24, 2025)
🏢 Organizations: Medable, BiopharmGuy
👤 Guests: Pamela Tenaerts, Sarah Chen
🎯 Patterns: Boss is Stuck, Innovation Pipeline
```

### Dry-run with JSON output (for automation)
```bash
./bin/extract-posts https://example.substack.com/p/post-title --dry-run --json
```

Output:
```json
{
  "status": "success",
  "url": "https://example.substack.com/p/post-title",
  "dry_run": true,
  "entities": {
    "posts": [
      {
        "name": "Post Title",
        "description": "Post description",
        "content_url": "https://...",
        "content_source": "substack",
        "published_at": "Oct 24, 2025"
      }
    ],
    "organizations": [...],
    "guests": [...],
    "patterns": [...],
    "pattern_post_link": [...],
    "pattern_org_link": [...],
    "pattern_guest_link": [...]
  }
}
```

### Debug mode
```bash
./bin/extract-posts https://example.substack.com/p/post-title --verbose
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Invalid arguments (bad URL) |
| 2 | Extraction/validation failure (HTTP error, LLM error, validation failed) |
| 3 | Database or environment error (DATABASE_URL, OPENAI_API_KEY missing, DB connection failed) |

## How It Works

The CLI reuses the existing extraction pipeline from the web UI:

1. **Extraction** (`agent_request_to_extract_entities`):
   - Fetches HTML from URL via HTTP GET
   - Calls OpenAI GPT-4o with `EXTRACT_CONTENT` system prompt (from YAML)
   - Parses JSON response containing: posts, patterns, organizations, guests, and link tables

2. **Validation** (`agent_verify_upsert`):
   - Validates payload structure (all required arrays present)
   - Checks required fields (name for entities, kind for patterns)
   - Validates referential integrity (link table references)
   - Safety checks (no SQL injection patterns)
   - Semantic validation (timestamps, source consistency)

3. **Database Upsert** (`tool.executeSQL` → `ExecuteUpsertTool`):
   - Calls PostgreSQL procedure: `CALL upsert_pattern_factory_entities(jsonb_payload, NULL)`
   - Procedure handles all upsertion logic and conflict resolution
   - Parameterized queries prevent SQL injection

## Troubleshooting

### DATABASE_URL not set
```
ERROR    | ❌ DATABASE_URL not set
```
Set `DATABASE_URL` in `.env`:
```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/pattern-factory"
```

### OPENAI_API_KEY not set
```
ERROR    | ❌ OPENAI_API_KEY not set
```
Set `OPENAI_API_KEY`:
```bash
export OPENAI_API_KEY="sk-..."
```

### Invalid URL
```
ERROR    | ❌ Invalid URL: ...
```
Ensure URL is valid HTTP/HTTPS. The tool will auto-prepend `https://` if no scheme is provided.

### Extraction failed / Validation failed
Use `--verbose` flag to see detailed error messages:
```bash
./bin/extract-posts <url> --verbose
```

Check logs for:
- HTTP status (404, 403, etc.)
- LLM response parsing errors
- Missing required fields in extracted entities
- Orphaned link references

### Database connection failed
```
ERROR    | ❌ Failed to connect to database: ...
```
Verify:
- PostgreSQL is running
- `DATABASE_URL` is correct
- Network connectivity
- Database user permissions

## Integration with CI/CD

Use `--dry-run --json` for automated testing:

```bash
#!/bin/bash
URL="https://..."
./bin/extract-posts "$URL" --dry-run --json | \
  python -c "import json, sys; data = json.load(sys.stdin); sys.exit(0 if data['status'] == 'success' else 1)"
```

## Development

To test the CLI during development:

```bash
# Run directly
python -m backend.cli.extract_posts https://example.com

# Or use the wrapper
./bin/extract-posts https://example.com

# With debugging
PYTHONUNBUFFERED=1 ./bin/extract-posts https://example.com -vv
```

## Notes

- URLs are normalized to HTTPS if no scheme is provided
- The tool supports Substack and any web content
- Extraction quality depends on LLM model and `EXTRACT_CONTENT` prompt quality
- `--dry-run` validates extraction but doesn't modify the database
- Large pages (>60KB) are truncated before sending to LLM for cost/latency reasons
