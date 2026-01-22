# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Pattern Factory is a full-stack application combining:
- **Frontend**: Svelte 5 + SvelteKit (TypeScript)
- **Backend**: Python FastAPI with async Postgres (asyncpg)
- **Database**: PostgreSQL 17
- **AI System**: Pitboss supervisor with LLM integration (OpenAI GPT-4o)

The application extracts patterns and antipatterns from podcast transcripts and Substack content using an AI-driven agent system, storing them with linked relationships across episodes, guests, organizations, and posts.

## Architecture Overview

### Backend Structure

**FastAPI API** (`backend/services/api.py`):
- RESTful endpoints for CRUD operations on patterns, episodes, guests, orgs, posts, models, threats, assets, vulnerabilities, countermeasures
- WebSocket endpoint at `/ws` for real-time agent communication
- Async Postgres connection pooling (asyncpg)
- Generic table query endpoint `/query/{table}`
- System logging via `system_log` table
- Mode system endpoints:
  - `POST /models/{model_id}/activate`: Set active model for current user
  - `GET /active-model`: Retrieve active model for current user
  - `GET /views?mode=explore|model`: Get views filtered by mode
  - Filtered views (`vthreats`, `vvulnerabilities`, `vcountermeasures`, `vassets`) that scope queries to active model

**Pitboss Supervisor** (`backend/pitboss/`):
- Orchestrates natural-language rule execution pipeline
- `supervisor.py`: Main orchestrator that chains tool execution
- `context_builder.py`: Builds LLM context from pattern-factory.yaml (SYSTEM + DATA sections)
- `tools.py`: Registry of async tools (sql_pitboss, data_table, register_rule, register_view)
- `config.py`: Configuration management for model settings, timeouts, and execution parameters

**Tool Pipeline**:
1. **sql_pitboss**: Converts natural-language rules to SQL via GPT-4o
2. **data_table**: Creates materialized views (CREATE TABLE AS SELECT)
3. **register_rule**: Writes rule metadata to `rules` table
4. **register_view**: Records view info in `views_registry` table

### Frontend Structure

**Pages** (`src/routes/`):
- `/+page.svelte`: Home/dashboard
- `/patterns/+page.svelte`: Pattern CRUD operations
- `/results/+page.svelte`: Display materialized views as DataTables
- Settings and help pages

**Components** (`src/lib/`):
- `Header.svelte`: Navigation, branding, and mode selector
- `Sidebar.svelte`: Mode-aware left navigation (Explore or Model mode)
- `modeStore.ts`: Svelte store for managing mode ('explore' | 'model') and activeModel state with localStorage persistence
- `DataTable.svelte`: Reusable table component using datatables.net
- `ResultsTables.svelte`: Multi-table results display
- `db.ts`: Database/API client utilities

**Mode System**:
- Two distinct workflows: Explore (patterns, cards, paths) and Model (models, threats, assets, vulnerabilities, countermeasures)
- Mode selector in header with underline active state (no background pills)
- Active model persisted in backend `public.active_models` table and restored on mode switch
- Context narration in header shows current mode or active model name
- Sidebar links automatically reflect current mode
- Active model row highlighted with pale green background in models table

### Data Model
**Pattern Factory YAML**
- Contains metadata for proper construction of system prompts as rules to generate logical views for the application

**Core Tables**:
- `patterns`: pattern definitions (id, name, description, kind, metadata, etc.)
- `episodes`, `guests`, `orgs`, `posts`: content sources
- `pattern_*_link`: Junction tables for many-to-many relationships
- `views_registry`: Materialized view metadata
- `system_log`: Event logging for auditing
- `users`: User account definitions
- `public.active_models`: User's active model mapping (one model per user)
- `threat.models`: Threat models for Model mode
- `threat.threats`, `threat.assets`, `threat.vulnerabilities`, `threat.countermeasures`: Model mode entities

**Derived Views** (created from rules):
- `pattern_episodes`, `pattern_guests`, `pattern_orgs`, `pattern_posts`: Pre-joined views

## Development Commands

### Frontend Development

```bash
# Install dependencies
npm install

# Run dev server (http://localhost:5173)
npm run dev

# Type checking (Svelte + TypeScript)
npm run check

# Watch type checking
npm run check:watch

# Build for production
npm run build

# Preview production build locally
npm run preview
```

### Backend Development

```bash
# Install Python dependencies
cd backend
pip install -r requirements.txt  # Create if missing; should include: fastapi uvicorn asyncpg openai python-dotenv pyyaml

# Run FastAPI dev server (http://localhost:8000)
# From backend directory:
uvicorn services.api:app --reload --host 0.0.0.0 --port 8000

# Run Pitboss supervisor in isolation (for testing)
python -m pitboss.supervisor
```

### CLI Tools

**Extract Posts** (`bin/extract-posts`):
Extract entities (posts, patterns, orgs, guests) from web URLs and upsert to database.

```bash
# Extract and upsert
./bin/extract-posts https://example.substack.com/p/post-title

# Validate without upserting (dry-run)
./bin/extract-posts https://example.substack.com/p/post-title --dry-run

# Get JSON output for automation
./bin/extract-posts https://example.substack.com/p/post-title --json

# Enable debug logging
./bin/extract-posts https://example.substack.com/p/post-title --verbose
```

Requires `DATABASE_URL` and `OPENAI_API_KEY` env vars. See `docs/CLI_EXTRACT_POSTS.md` for full documentation.

### Database Setup

```bash
# PostgreSQL (assuming local installation with defaults from .env)
psql -h 127.0.0.1 -U pattern_factory -d pattern-factory

# Create database and schema (one-time setup)
# Use database migration scripts from backend/db/ directory

# Connect and verify
psql postgresql://pattern_factory:314159@localhost:5432/pattern-factory -c "\dt"
```

### Testing

```bash
# Frontend tests (if configured)
npm run test  # Currently minimal test setup

# Backend tests (create as needed)
# Pattern: python -m pytest backend/tests/ -v
```

## Key Configuration

### Environment Variables (.env)

**Database**:
- `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`, `PGPASSWORD`: PostgreSQL connection
- `DATABASE_URL`: Full connection string format

**API**:
- `API_HOST`, `API_PORT`: FastAPI server binding (default: 0.0.0.0:8000)

**AI/LLM**:
- `OPENAI_API_KEY`: GPT-4o API key (required for pattern extraction)
- `PITBOSS_STRATEGY`: llm_supervised (default)

**Frontend**:
- `VITE_API_BASE`: API endpoint for frontend (default: http://localhost:8000)

See `.env.example` for template.

## Important Files and Patterns

### Pattern Factory YAML (`prompts/rules/pattern-factory.yaml`)

Defines the DSL schema:
- `SYSTEM.prompt`: Instructions for LLM (model_rule_agent)
- `DATA.tables`: Complete schema description (used by ContextBuilder)
- `RULES`: Predefined rules that users can execute (examples for the LLM)

Changes here affect SQL generation quality. Keep table/column descriptions accurate.

### Message Protocol v1.1 (Put-and-Take Pattern)

The system implements a stateless "put-and-take" message protocol between frontend and backend:

Message Envelope Structure:
```json
{
  "type": "request" | "response" | "error",
  "version": "1.1",
  "session_id": "sess-...",
  "request_id": "req-...",
  "verb": "RULE" | "CONTENT" | "GENERIC",
  "nextAgent": "agent-name" | null,
  "decision": "yes" | "no" | null,
  "confidence": 0.0-1.0,
  "reason": "explanation",
  "returnCode": 0 | 1 | -1,
  "messageBody": { "...": "user and agent payload" }
}
```

Flow:
1. Frontend sends REQUEST with `verb: GENERIC`, `nextAgent: model.LanguageCapo`.
2. Backend returns RESPONSE with `nextAgent` indicating the next agent to call.
3. Frontend MUST NOT modify `nextAgent`; it echoes back as received.
4. Frontend echoes `messageBody` from the backend response (e.g., preserves `sql_query`, `rule_code`).
5. Frontend may add `raw_text` to `messageBody` for user comments/approval.

HITL (Human-In-The-Loop):
- When an agent returns `decision: "no"`, frontend detects HITL.
- Frontend stores full `messageBody` and, on user reply, echoes it back with the SAME `verb` and SAME `nextAgent`.
- Backend routes directly to `nextAgent` without reclassification.

Backend HITL mapping:
- `WorkflowEngine.get_hitl_next_agent(verb, current_agent)` defines resume targets.
  - RULE: `model.verifySQL` → `tool.executeSQL`.
- `supervisor.py` uses `nextAgent` from the envelope to jump to the correct agent when present.

### Pitboss Processing Flow (Legacy)

1. WebSocket `/ws` receives JSON: `{"type": "run_rule", "rule_code": "...", "rule_id": "..."}`
2. Supervisor calls ContextBuilder to assemble system + user prompts
3. SqlPitbossTool calls OpenAI to generate SQL (async via thread pool)
4. DataTableTool executes SQL and creates materialized table
5. RegisterRuleTool records rule metadata
6. RegisterViewTool registers view in views_registry
7. Results sent back over WebSocket as JSON

### API Response Patterns

All tool responses follow:
```json
{
  "status": "success" | "error",
  "error": "...",
  "duration": 1.23
}
```

Plus tool-specific fields (e.g., `sql`, `table_name`, `row_count`).

## Common Development Tasks

### Adding a New Pattern Source

1. Add table to PostgreSQL schema
2. Update `DATA.tables` in `pattern-factory.yaml`
3. Create new junction table if needed (e.g., `pattern_newsitem_link`)
4. Add corresponding derived view definition

### Creating a New Rule

Users add rules via the web UI; for static definitions, edit `RULES` section in `pattern-factory.yaml`.

### Understanding the Mode System

The application supports two modes:
- **Explore Mode**: Browse and manage patterns, paths, and cards. Left sidebar shows navigation for these entities.
- **Model Mode**: Manage threat models and their entities (threats, assets, vulnerabilities, countermeasures). Left sidebar shows navigation for these entities.

Mode state is managed by `modeStore` (`src/lib/modeStore.ts`) and persisted to localStorage. The active model is stored in `public.active_models` backend table for persistence across sessions. When switching to Model mode, the frontend fetches the active model from the backend via `GET /active-model` endpoint and restores it.

Key components:
- Mode selector in header (`Explore` | `Model`) with underline on active state
- Header context narration shows "Explore mode" or "Model: {name}"
- Sidebar links reflect current mode
- Active model highlighted with pale green background in models table

### Mode-Aware Views in Sidebar

The sidebar's Views section is filtered by the current application mode. Each view in `public.views_registry` has a `mode` column (default: 'explore') that determines visibility.

**Backend**: `GET /views?mode=explore|model` endpoint filters views_registry by mode.

**Frontend**: Sidebar subscribes to `modeStore` and automatically fetches the appropriate views when mode changes.

**Database**: `public.views_registry` table includes:
- `mode`: TEXT default 'explore' - Controls which mode(s) show this view
- Views with mode='explore' appear only in Explore mode
- Views with mode='model' appear only in Model mode
- New views default to 'explore' if mode is not specified

**Usage**: When creating new views via the Pitboss rule system, set the `mode` column appropriately. For materialized views that should only appear in Model mode, update the views_registry entry after creation.

### Debugging Pitboss

- Enable logging: `logging.basicConfig(level=logging.DEBUG)` in supervisor.py
- Check `system_log` table for event records
- Verify OpenAI key and rate limits
- Inspect WebSocket messages in browser DevTools

### Database Schema Changes

1. Create migration script in `backend/db/`
2. Document schema in `pattern-factory.yaml` DATA section
3. Restart FastAPI to reload schema

## UI/Form Design Guidelines

All forms and entity pages must follow a single, consistent UI pattern across the application. This ensures a unified user experience and reduces maintenance burden.

### Index Pages
- Display entities in a list/table of rows
- "Add [Entity]" button positioned on the right side
- Each row has a pencil icon (or pencil + trash if deletion enabled)
- Row click (not icon) → navigate to view/id to see entity details
- Pencil icon click → navigate to edit/id for editing

### Add Entity Modal Popup
- Modal popup (not a full page)
- Fields: name and description ONLY (no other fields)
- Button labels: Cancel, Save (not "Create")
- Users add additional details in the Edit entity form
- Example: Add Pattern modal shows only name + description

### View Entity Page
- Reached by clicking a row on index page (navigate to view/id)
- Page header: "[Entity Type]" (e.g., "Threats") styled as `heading heading-1`
- Entity name (e.g., "Unauthorized Remote Control") displayed inside card styled as `heading heading-3`
- Green EDIT button on right side → moves to edit mode
- No breadcrumb links or return buttons (use sidebar for navigation)

### Edit Entity Page
- Regular form page (not modal popup)
- Reached from pencil icon or EDIT button on view page
- Navigate to edit/id
- Form buttons positioned bottom right:
  - **For entities WITH Markdown stories** (Patterns, Cards): Cancel, Edit Story, Save
  - **For entities WITHOUT stories** (Threats, Assets, etc.): Cancel, Save
- No breadcrumb links or return buttons

### Styling Rules
- Use ONLY standard main.css classes
- No inline styles or page-scoped CSS in form components
- No custom component-specific styles
- Heading classes: `heading heading-1` for page titles, `heading heading-3` for entity names in cards
- Button classes: `big-blue-button` for EDIT and Save buttons
- Follow existing main.css for all spacing, typography, colors

### Select Boxes (Autocomplete)
- Display matching entries BELOW the select box as user types
- Autocomplete fires dynamically on input
- Example: Selecting cards in threat form shows matching cards below the input

### External Link Icons
- When displaying links to related entities (e.g., card names linking to card details), use a small superscript arrow (↗) positioned inline at the top right of the text
- Use `vertical-align: super` to position the arrow, NOT absolute positioning
- Arrow styling: `font-size: 9px; color: #0066cc; text-decoration: none; vertical-align: super; margin-left: 2px;`
- The link should open in a new tab: `target="_blank" rel="noopener noreferrer"`
- Include title attribute for accessibility: `title="View details"`

### Implementation Checklist
- Convert all modal patterns/cards forms to regular form pages
- Ensure all entity types (threats, assets, vulnerabilities, countermeasures, models) follow same pattern
- Button positioning: always bottom right for form controls
- Row interaction: row click = view, icon click = edit

## Technology Stack Details

- **Svelte 5**: Latest reactive framework with runes
- **SvelteKit**: File-based routing and SSR
- **DataTables.net**: Advanced table UI with sorting, filtering, export
- **Flowbite**: Pre-built UI components
- **CodeMirror**: SQL/Python syntax highlighting (for future IDE features)
- **asyncpg**: Async Postgres driver (faster than psycopg2)
- **FastAPI**: Modern async Python framework with automatic OpenAPI docs
- **OpenAI API**: GPT-4o for natural language → SQL translation
- **WebSockets**: Real-time frontend-backend communication for agent progress
