"""
services/api.py
Clean and production-ready Pattern Factory API (Postgres + Pitboss).
"""

import os
import json
import logging
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import asyncpg
from dotenv import load_dotenv
from openai import OpenAI

# -------------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pattern-factory.api")
logger.info("📦 Loading Pattern Factory API (clean version)")

# -------------------------------------------------------------------------
# Environment
# -------------------------------------------------------------------------
load_dotenv()

PGHOST      = os.getenv("PGHOST", "127.0.0.1")
PGPORT      = os.getenv("PGPORT", "5432")
PGUSER      = os.getenv("PGUSER", "pattern_factory")
PGDATABASE  = os.getenv("PGDATABASE", "pattern_factory")
PGPASSWORD  = os.getenv("PGPASSWORD", "314159")

POSTGRES_DSN = f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# -------------------------------------------------------------------------
# FastAPI Init with CORS
# -------------------------------------------------------------------------
app = FastAPI(
    title="Pattern Factory API",
    description="Backend API (Postgres + Pitboss)",
    version="2.1.0"
)

# Add CORS middleware FIRST before any routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PG_POOL: Optional[asyncpg.Pool] = None

# -------------------------------------------------------------------------
# Import Pitboss Supervisor
# -------------------------------------------------------------------------
from pitboss.supervisor import PitbossSupervisor
logger.info("🧠 Imported Pitboss Supervisor successfully")

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def get_pg_pool() -> asyncpg.Pool:
    if PG_POOL is None:
        raise RuntimeError("Postgres pool not initialized")
    return PG_POOL

# -------------------------------------------------------------------------
# Startup: connect to Postgres
# -------------------------------------------------------------------------
@app.on_event("startup")
async def startup_postgres():
    global PG_POOL
    logger.info(f"🐘 Connecting to Postgres: {POSTGRES_DSN}")

    PG_POOL = await asyncpg.create_pool(
        dsn=POSTGRES_DSN,
        min_size=1,
        max_size=5
    )

    # Ensure system_log exists
    async with PG_POOL.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS system_log (
            id SERIAL PRIMARY KEY,
            event TEXT,
            context JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

    logger.info("✅ Postgres connected and system_log ready")

# -------------------------------------------------------------------------
# Shutdown: clean close
# -------------------------------------------------------------------------
@app.on_event("shutdown")
async def shutdown_postgres():
    if PG_POOL:
        await PG_POOL.close()
        logger.info("🧹 Closed Postgres pool")

# -------------------------------------------------------------------------
# Optional OpenAI diagnostics
# -------------------------------------------------------------------------
@app.on_event("startup")
async def startup_openai():
    if not OPENAI_API_KEY:
        logger.warning("⚠️ No OPENAI_API_KEY set — skipping diagnostics")
        return

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        models = [m.id for m in client.models.list().data[:3]]
        logger.info(f"🧠 OpenAI models: {', '.join(models)}")
    except Exception as e:
        logger.warning(f"⚠️ OpenAI diagnostics failed: {e}")

# -------------------------------------------------------------------------
# Root Endpoint
# -------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Pattern Factory API operational",
        "postgres": POSTGRES_DSN,
        "timestamp": datetime.now().isoformat()
    }

# -------------------------------------------------------------------------
# GET /patterns
# -------------------------------------------------------------------------
@app.get("/patterns")
async def get_patterns():
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, description, kind, story_md, taxonomy, created_at, updated_at
            FROM patterns
            ORDER BY created_at DESC
        """)

    return [dict(r) for r in rows]

# Create a new pattern
from pydantic import BaseModel

class PatternCreate(BaseModel):
    name: str
    description: str
    kind: str
    story_md: str | None = None
    taxonomy: str | None = None

@app.get("/patterns/{pattern_id}", tags=["Patterns"])
async def get_pattern(pattern_id: int):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, description, kind, story_md, taxonomy, created_at, updated_at
            FROM patterns
            WHERE id = $1
            """,
            pattern_id
        )
    if not row:
        return {"error": f"Pattern {pattern_id} not found"}
    return dict(row)

@app.post("/patterns", tags=["Patterns"])
async def create_pattern(pattern: PatternCreate):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO patterns (name, description, kind, story_md, taxonomy)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, name, description, kind, story_md, taxonomy, created_at, updated_at
            """,
            pattern.name,
            pattern.description,
            pattern.kind,
            pattern.story_md,
            pattern.taxonomy
        )
        return dict(row)
# Upda
class PatternUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    kind: str | None = None
    story_md: str | None = None
    taxonomy: str | None = None

@app.put("/patterns/{pattern_id}", tags=["Patterns"])
async def update_pattern(pattern_id: int, patch: PatternUpdate):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE patterns
            SET 
                name = COALESCE($1, name),
                description = COALESCE($2, description),
                kind = COALESCE($3, kind),
                story_md = COALESCE($4, story_md),
                taxonomy = COALESCE($5, taxonomy),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $6
            RETURNING id, name, description, kind, story_md, taxonomy, created_at, updated_at
            """,
            patch.name,
            patch.description,
            patch.kind,
            patch.story_md,
            patch.taxonomy,
            pattern_id
        )
        if not row:
            return {"error": f"Pattern {pattern_id} not found"}
        return dict(row)
# Delete pattern
@app.delete("/patterns/{pattern_id}", tags=["Patterns"])
async def delete_pattern(pattern_id: int):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM patterns WHERE id = $1", pattern_id
        )
        # asyncpg returns: "DELETE 1" or "DELETE 0"
        if result == "DELETE 0":
            return {"error": f"Pattern {pattern_id} not found"}
    return {"status": "ok", "deleted_id": pattern_id}

# -------------------------------------------------------------------------
# Paths CRUD
# -------------------------------------------------------------------------
class PathNode(BaseModel):
    id: str
    type: str  # assumption, decision, state
    label: str
    serial: Optional[int] = None
    optionality: Optional[dict] = None  # {collapses: bool, reason: str}

class PathEdge(BaseModel):
    from_node: str  # node id
    to_node: str    # node id
    reason: str

class PathCreate(BaseModel):
    name: str
    nodes: list[PathNode] = []
    edges: list[PathEdge] = []

class PathUpdate(BaseModel):
    name: Optional[str] = None
    nodes: Optional[list[PathNode]] = None
    edges: Optional[list[PathEdge]] = None
    youAreHere: Optional[int] = None

@app.get("/paths")
async def get_paths():
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, yaml, created_at, updated_at
            FROM paths
            ORDER BY created_at DESC
        """)
    
    result = []
    for row in rows:
        r = dict(row)
        # Parse yaml field if it exists
        if r.get('yaml'):
            try:
                r['yaml'] = json.loads(r['yaml'])
            except:
                pass
        result.append(r)
    return result

@app.post("/paths", tags=["Paths"])
async def create_path(path: PathCreate):
    pool = get_pg_pool()
    
    # Build YAML structure - pass through frontend data as-is
    yaml_data = {
        "nodes": [n.model_dump() for n in path.nodes],
        "edges": [e.model_dump() for e in path.edges]
    }
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO paths (name, yaml)
            VALUES ($1, $2)
            RETURNING id, name, yaml, created_at, updated_at
            """,
            path.name,
            json.dumps(yaml_data)
        )
        r = dict(row)
        if r.get('yaml'):
            r['yaml'] = json.loads(r['yaml'])
        return r

@app.get("/paths/{path_id}")
async def get_path(path_id: int):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, yaml, created_at, updated_at FROM paths WHERE id = $1",
            path_id
        )
    
    if not row:
        raise HTTPException(status_code=404, detail="Path not found")
    
    r = dict(row)
    if r.get('yaml'):
        try:
            r['yaml'] = json.loads(r['yaml'])
        except:
            pass
    return r

@app.put("/paths/{path_id}", tags=["Paths"])
async def update_path(path_id: int, patch: PathUpdate):
    pool = get_pg_pool()
    
    # Build updated YAML if any data provided
    yaml_data = None
    if patch.nodes is not None or patch.edges is not None or patch.youAreHere is not None:
        # Fetch current data first
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT yaml FROM paths WHERE id = $1", path_id
            )
        
        if not row:
            raise HTTPException(status_code=404, detail="Path not found")
        
        current_yaml = {}
        if row['yaml']:
            try:
                current_yaml = json.loads(row['yaml'])
            except:
                pass
        
        # Update with new values - pass through frontend data as-is
        if patch.nodes is not None:
            current_yaml['nodes'] = [n.model_dump() for n in patch.nodes]
        if patch.edges is not None:
            current_yaml['edges'] = [e.model_dump() for e in patch.edges]
        if patch.youAreHere is not None:
            current_yaml['youAreHere'] = patch.youAreHere
        
        yaml_data = json.dumps(current_yaml)
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE paths
            SET 
                name = COALESCE($1, name),
                yaml = COALESCE($2, yaml),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $3
            RETURNING id, name, yaml, created_at, updated_at
            """,
            patch.name,
            yaml_data,
            path_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Path not found")
        
        r = dict(row)
        if r.get('yaml'):
            try:
                r['yaml'] = json.loads(r['yaml'])
            except:
                pass
        return r

@app.delete("/paths/{path_id}", tags=["Paths"])
async def delete_path(path_id: int):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM paths WHERE id = $1", path_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Path not found")
    return {"status": "ok", "deleted_id": path_id}

# -------------------------------------------------------------------------
# GET /query/{table}  (Universal table reader)
# -------------------------------------------------------------------------
@app.get("/query/{table}")
async def query_table(table: str, limit: int = 200):
    """
    Generic SQL reader for any table.
    
    For registered views, table name is the YAML rule_code (e.g., LIST_ORGS).
    For other tables, queries directly.
    """
    pool = get_pg_pool()

    # Basic sanitization to block SQL injection
    if not table.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid table name")

    async with pool.acquire() as conn:
        try:
            # Query the table/view directly by name
            # View names are rule_codes (e.g., LIST_ORGS)
            rows = await conn.fetch(f'SELECT * FROM "{table}" LIMIT {limit}')
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    return [dict(r) for r in rows]

# -------------------------------------------------------------------------
# WebSocket → Pitboss
# -------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 WebSocket connected")

    # Create Pitboss instance
    pitboss = PitbossSupervisor(db_connection=get_pg_pool(), websocket=websocket)
    logger.info("🧠 Pitboss instance created for WebSocket")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            # Routing: Message Protocol (v1.1) vs legacy "run_rule"
            if msg.get("type") in ["request", "response", "error"]:
                # New envelope-based protocol
                logger.info(f"📨 Received envelope: verb={msg.get('verb')}, nextAgent={msg.get('nextAgent')}")
                await pitboss.process_envelope(msg)
            elif msg.get("type") == "run_rule":
                # Legacy rule execution (still supported for backwards compatibility)
                await pitboss.process_rule_request(
                    rule_code=msg.get("rule_code"),
                    rule_id=msg.get("rule_id")
                )
            else:
                await websocket.send_json({"type": "echo", "message": msg})

    except WebSocketDisconnect:
        logger.info("🔌 WebSocket disconnected")
    finally:
        try:
            await websocket.close()
        except:
            pass

# -------------------------------------------------------------------------
# POST /log
# -------------------------------------------------------------------------
@app.post("/log")
async def write_log(event: str, context: dict = {}):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO system_log (event, context) VALUES ($1, $2)",
            event, json.dumps(context)
        )
    return {"status": "ok", "event": event}

# -------------------------------------------------------------------------
# Final banner
# -------------------------------------------------------------------------
logger.info(f"""
==========================================
🔥 Pattern Factory API Ready
🐘 Database: {POSTGRES_DSN}
🔑 OpenAI key prefix: {OPENAI_API_KEY[:8] if OPENAI_API_KEY else 'MISSING'}
📡 WebSocket: /ws
🔍 Query: /query/{{table}}
📚 Patterns: /patterns
==========================================
""")
