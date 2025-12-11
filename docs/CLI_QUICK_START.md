# Extract-Posts CLI Quick Start

## Installation

The CLI is part of the Pattern Factory project. No separate installation needed—it's ready to use!

```bash
# Make sure you're in the pattern-factory directory
cd /Users/dl/code/pattern-factory

# Test that it works
./bin/extract-posts --help
```

## Setup

1. **Ensure environment variables are set:**

```bash
# Add to your .env file or shell
export DATABASE_URL="postgresql://user:password@localhost:5432/pattern-factory"
export OPENAI_API_KEY="sk-..."
```

2. **PostgreSQL must be running:**

```bash
# Check if PostgreSQL is running
psql -c "SELECT version();"
```

3. **Have Python 3.9+ and dependencies installed:**

```bash
cd backend
pip install -r requirements.txt
```

## First Extraction

```bash
# Extract from a Substack post
./bin/extract-posts https://example.substack.com/p/the-great-brain-bet
```

Expected output:
```
✅ Success!

📰 Post: 'The Great Brain Bet: How Human-derived mini-brains...' (Oct 24, 2025)
🏢 Organizations: Medable, BiopharmGuy
👤 Guests: Pamela Tenaerts, Sarah Chen
🎯 Patterns: Boss is Stuck, Innovation Pipeline
```

## Common Tasks

### 1. Preview extraction without database changes
```bash
./bin/extract-posts <url> --dry-run
```

### 2. Get JSON for processing in scripts
```bash
./bin/extract-posts <url> --json | jq '.entities.posts'
```

### 3. See detailed logging (for debugging)
```bash
./bin/extract-posts <url> --verbose
```

### 4. Check help
```bash
./bin/extract-posts --help
```

## Troubleshooting

### Command not found
```
-bash: ./bin/extract-posts: No such file or directory
```
Make sure you're in the `pattern-factory` directory and the file is executable:
```bash
ls -la bin/extract-posts  # Should show -rwxr-xr-x
chmod +x bin/extract-posts  # If needed
```

### DATABASE_URL not set
```
ERROR    | ❌ DATABASE_URL not set
```
Set the environment variable:
```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/pattern-factory"
```

### Connection refused
```
ERROR    | ❌ Failed to connect to database: ...
```
PostgreSQL is not running. Start it:
```bash
# macOS with Homebrew
brew services start postgresql

# Or check if it's already running
psql -c "SELECT 1;"
```

### OPENAI_API_KEY not set
```
ERROR    | ❌ OPENAI_API_KEY not set
```
Set your OpenAI API key:
```bash
export OPENAI_API_KEY="sk-..."
```

## Full Documentation

See [`docs/CLI_EXTRACT_POSTS.md`](CLI_EXTRACT_POSTS.md) for complete documentation including:
- Exit codes
- All flags and options
- Integration with CI/CD
- Batch processing
- API usage

## Examples

### Extract multiple URLs
```bash
for url in $(cat my_urls.txt); do
  echo "Processing $url..."
  ./bin/extract-posts "$url"
done
```

### Extract with JSON output for automation
```bash
result=$(./bin/extract-posts "$url" --json)
status=$(echo "$result" | jq -r '.status')
if [ "$status" = "success" ]; then
  echo "✅ Extraction successful"
  echo "$result" | jq '.entities.patterns'
else
  echo "❌ Extraction failed"
fi
```

### Validate extraction before committing
```bash
./bin/extract-posts "$url" --dry-run && \
  ./bin/extract-posts "$url" && \
  echo "✅ All good!"
```

## Tips

- **URL normalization**: Auto-adds `https://` if you omit the scheme. `example.com` → `https://example.com`
- **Dry-run is your friend**: Use `--dry-run` to test extraction before upserting
- **JSON output**: Perfect for scripting and CI/CD pipelines
- **Verbose mode**: Use `--verbose` when things go wrong to see detailed logs
- **Check help**: `./bin/extract-posts --help` for all options

## Getting Help

1. Check documentation: `docs/CLI_EXTRACT_POSTS.md`
2. Run with verbose: `./bin/extract-posts <url> --verbose`
3. Review error message carefully (they're designed to be helpful!)
4. Check database/environment setup

## Next Steps

- Read `docs/CLI_EXTRACT_POSTS.md` for full documentation
- Try dry-run first: `./bin/extract-posts <url> --dry-run`
- Integrate with your workflow
- Automate with scripts

Happy extracting! 🎉
