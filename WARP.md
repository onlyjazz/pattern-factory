# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Pattern Factory - a SvelteKit frontend with FastAPI/Python backend that processes DSL (Domain Specific Language) rules to identify data anomalies in clinical trial datasets. The application uses AI agents to convert clinical trial rules into SQL queries and analyze the results.

## Tech Stack

### Frontend
- **Framework**: SvelteKit with Svelte 5
- **UI Components**: Flowbite + Tailwind CSS v4
- **Code Editor**: CodeMirror
- **Build Tool**: Vite
- **Desktop Support**: Tauri (optional)
- **Tables**: DataTables.net

### Backend
- **API Framework**: FastAPI with Uvicorn
- **Database**: DuckDB (embedded analytics database)
- **AI/ML**: OpenAI GPT-4 for rule-to-SQL conversion
- **WebSocket**: For real-time rule execution
- **Python Version**: 3.13.3 (via pyenv)

## Common Development Commands

### Environment Setup
```bash
# Set up Python environment (first time)
pyenv install 3.13.3
pyenv global 3.13.3
cd services/
pip install pip-tools
pip-compile requirements.in
pip-sync requirements.txt

# Install Node dependencies
npm install

# Set up environment variables
cp .env.example .env  # Then edit with your values
```

### Running the Application
```bash
# Start backend API server (port 8000)
python -m services.run
# OR
python services/api.py

# Start WebSocket server (port 8002)
python services/server.py

# Start frontend dev server (port 5173)
npm run dev

# Run both frontend and backend (if configured)
make dev
```

### Building and Testing
```bash
# Build frontend
npm run build

# Type check
npm run check

# Build DSL parser
npm run build:parser

# Run Tauri desktop app
npm run tauri
```

### Git Workflow Commands (from Makefile)
```bash
# Create new feature branch
make start BRANCH=cycle2-my-feature

# Rebase feature branch on base
make rebase-feature BRANCH=cycle2-my-feature

# Clean up merged branches
make clean-merged
```

## Architecture Overview

### Message Flow
1. **User Input**: User types command in AI Chat (frontend)
2. **WebSocket Communication**: Frontend extracts rule from DSL and sends via WebSocket
3. **Pitboss Orchestration**: Backend orchestrates three agents:
   - **Language Agent**: Converts rule logic to SQL (via GPT-4)
   - **Tool Agent**: Executes SQL against DuckDB
   - **Callback Agent**: Sends results back to frontend
4. **Results Display**: Results shown in AI Chat as summary messages

### Key Services

#### API Server (`services/api.py`)
- FastAPI application on port 8000
- Handles CRUD operations for protocols, rules, alerts, cards
- Manages DuckDB connections with thread locking
- Provides RESTful endpoints for frontend

#### WebSocket Server (`services/server.py`)
- Runs on port 8002
- Processes rule execution requests
- Handles DSL workflow execution
- Real-time communication with frontend

#### Pitboss (`services/pitboss.py`)
- Central orchestrator for AI agents
- Manages rule-to-SQL conversion
- Executes database queries
- Formats and returns results

### Data Model
- `protocols`: Study/protocol metadata
- `rules`: Rule definitions and execution history
- `alerts`: Flagged records and summary counts
- `cards`: System prompts for different agents
- `ddt`: Data dictionary table
- Result tables: Materialized as `{protocol_id}_{rule_id}`

## DSL Structure

The application uses YAML-based DSL files (e.g., `clovis.yaml`) with sections:
- **PROTOCOL**: Metadata (ID, version)
- **DATA**: Required tables and columns
- **RULES**: Alert definitions with logic
- **WORKFLOW**: Execution flow control

## Frontend Routes

- `/` - Main dashboard
- `/studies` - Study/protocol management
- `/actions` - Actions hub
  - `/actions/rules` - Rule management
  - `/actions/alerts` - Alert viewing
  - `/actions/workflow` - Workflow execution
  - `/actions/ddt` - Data dictionary
- `/cards` - System prompt management
- `/code` - Code editor interface
- `/results` - Query results display

## Environment Variables (.env)

```env
# Database
DATABASE_URL=duckdb://~/code/data-review-database/datareview
DATABASE_LOCATION=~/code/data-review-database/datareview

# API
API_HOST=0.0.0.0
API_PORT=8000

# OpenAI
OPENAI_API_KEY=<your-key-here>

# Database Type
DB_TYPE=duckdb
```

## AI Chat Commands

### Command Formats
- `run RULE_ID` - Execute specific rule by ID from DSL
- `run SELECT ...` - Execute direct SQL
- `run [natural language]` - Convert to SQL via GPT-4
- `run` - Execute entire workflow

### Rule Processing
1. First checks if text matches a `rule_code` in DSL
2. If no match, treats as SQL or natural language
3. Uses system prompt from cards table for SQL generation

## Key Components to Understand

### Frontend State Management
- `selectedStudy.ts` - Current protocol context
- `dslStore.ts` - DSL content management
- `workflowStore.ts` - Workflow execution state
- `chat/store.ts` - AI chat message handling

### Backend Agent System
- Language Agent - GPT-4 integration for rule conversion
- Tool Agent - Database query execution
- Callback Agent - Result formatting and WebSocket messaging

### Recent Improvements (from .warp_rules.md)
- Date formatting utilities
- CodeMirror integration for system prompts
- Improved WebSocket message handling
- Summary message format for rule results
- DSL workflow execution support

## Database Access

The application uses DuckDB with thread locking for concurrent access. Always use the lock when accessing the database:

```python
with duckdb_lock:
    results = conn.execute(query).fetchall()
```

## Testing WebSocket Connection

```python
# From test_files/websocket.py
import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:8002/ws"
    async with websockets.connect(uri) as websocket:
        message = {
            "rule_code": "SELECT * FROM adlb WHERE alt > 100",
            "protocol_id": "CO-101-001",
            "rule_id": "ALT_HIGH"
        }
        await websocket.send(json.dumps(message))
        response = await websocket.recv()
        print(response)
```

## Important Files to Reference

- `/services/pitboss.py` - Core orchestration logic
- `/services/api.py` - REST API endpoints
- `/src/lib/AiChat.svelte` - AI chat interface
- `/src/lib/api.ts` - Frontend API client
- `/clovis.yaml` - Example DSL structure
- `/.warp_rules.md` - Recent improvements documentation