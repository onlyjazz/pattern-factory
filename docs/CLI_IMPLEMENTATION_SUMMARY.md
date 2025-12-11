# Extract-Posts CLI Implementation Summary

## Overview

A command-line interface for extracting entities (posts, patterns, organizations, guests) from web content and upserting them to the Pattern Factory database.

## What Was Created

### Core Files

1. **`backend/cli/__init__.py`**
   - Empty init file for Python module

2. **`backend/cli/extract_posts.py`** (346 lines)
   - Main CLI module
   - Reuses existing agents and tools from the web UI pipeline
   - Supports flags: `--dry-run`, `--json`, `--verbose`
   - Exit codes: 0 (success), 1 (bad args), 2 (extraction/validation error), 3 (env/DB error)

3. **`bin/extract-posts`** (shell wrapper)
   - Executable wrapper script that runs the Python module
   - Handles path resolution for portability

4. **`docs/CLI_EXTRACT_POSTS.md`** (208 lines)
   - Complete user documentation
   - Examples, troubleshooting, integration guide
   - Exit code reference

5. **`tests/test_cli_extract_posts.py`** (183 lines)
   - Integration tests for CLI
   - Tests URL validation, help, error handling
   - Optional integration test with live DB/LLM

6. **`WARP.md` update**
   - Added CLI Tools section with quick reference

## Architecture & Reuse

The CLI directly invokes existing backend components:

```
extract-posts <url>
    ↓
backend.cli.extract_posts.main()
    ↓
[1] agent_request_to_extract_entities()  ← Reused from agents.py
    • HTTP GET fetch
    • LLM extraction (EXTRACT_CONTENT prompt)
    • Returns JSON: {posts, patterns, orgs, guests, links}
    ↓
[2] agent_verify_upsert()  ← Reused from agents.py
    • Structural validation
    • Required field checks
    • Referential integrity
    • Safety checks
    ↓
[3] tool_registry.execute("execute_upsert")  ← Reused from tools.py
    • Calls PostgreSQL upsert procedure
    • Handles conflict resolution
    ↓
Output: Summary (default) or JSON (--json flag)
```

## Key Design Decisions

1. **No Supervisor Required**
   - CLI bypasses the WebSocket supervisor entirely
   - Directly instantiates ContextBuilder and ToolRegistry
   - Simpler async/await control flow

2. **Reuse Over Reimplementation**
   - All business logic (extraction, validation, upsert) comes from existing agents/tools
   - Only CLI orchestration and formatting is new
   - Ensures parity between web UI and CLI

3. **Environment Configuration**
   - Uses same env vars: `DATABASE_URL`, `OPENAI_API_KEY`
   - Fails fast with clear error messages if env is missing

4. **Output Options**
   - Human-readable summary by default (emoji-enhanced)
   - `--json` for automation/scripting
   - `--verbose` for debugging

5. **Non-Destructive Testing**
   - `--dry-run` validates extraction without upserting
   - Useful for CI/CD, preview, testing

## Usage Examples

### Basic extraction
```bash
./bin/extract-posts https://example.substack.com/p/post-title
```

Output:
```
✅ Success!

📰 Post: 'The Great Brain Bet: How Human-derived mini-brains...' (Oct 24, 2025)
🏢 Organizations: Medable, BiopharmGuy
👤 Guests: Pamela Tenaerts
🎯 Patterns: Boss is Stuck
```

### Automation (dry-run + JSON)
```bash
./bin/extract-posts https://example.com --dry-run --json | jq .entities
```

### Debug mode
```bash
./bin/extract-posts https://example.com --verbose
```

## Testing

Basic tests run without DB/LLM:
```bash
cd pattern-factory
python tests/test_cli_extract_posts.py
```

Output:
```
======================================================================
🧪 Extract-Posts CLI Integration Tests
======================================================================

🧪 Testing URL validation and normalization...
✅ example.com → https://example.com
...

✅ All tests passed!
======================================================================
```

## Exit Codes

| Code | Scenario |
|------|----------|
| 0 | Success |
| 1 | Invalid URL |
| 2 | Extraction/validation error (HTTP, LLM, validation failed) |
| 3 | Environment/database error (missing env vars, DB connection failed) |

## Integration Points

### CI/CD Pipeline
```bash
# Check extraction validity before deploying
./bin/extract-posts "$URL" --dry-run --json && echo "✅ Valid"
```

### Batch Processing
```bash
# Extract multiple URLs
for url in $(cat urls.txt); do
  ./bin/extract-posts "$url" --verbose
done
```

### API Integration (Python)
```python
import subprocess
import json

result = subprocess.run(
    ["./bin/extract-posts", url, "--json"],
    capture_output=True,
    text=True,
)
data = json.loads(result.stdout)
```

## Files Modified

- `WARP.md`: Added CLI Tools section with quick reference and link to docs

## Files Created

- `backend/cli/__init__.py`
- `backend/cli/extract_posts.py`
- `bin/extract-posts`
- `docs/CLI_EXTRACT_POSTS.md`
- `tests/test_cli_extract_posts.py`
- `docs/CLI_IMPLEMENTATION_SUMMARY.md` (this file)

## Future Enhancements

1. **Batch Processing**: Accept multiple URLs from stdin or file
2. **Format Options**: Support CSV, XML output formats
3. **Rate Limiting**: Add `--rate-limit` for batch operations
4. **Filtering**: Pre-extract filters (e.g., only patterns, skip orgs)
5. **Configuration File**: Support `.extract-posts.yml` for default flags
6. **Progress Tracking**: Show extraction progress for long operations

## Notes

- Module is backward compatible with existing web UI agents/tools
- No changes to agent or tool logic—only CLI wrapper added
- All extraction quality depends on YAML `EXTRACT_CONTENT` prompt
- Large pages (>60KB) are auto-truncated for LLM cost/latency
- CLI is async throughout for performance
