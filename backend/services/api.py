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
            SELECT id, name, description, kind, created_at, updated_at
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

@app.post("/patterns", tags=["Patterns"])
async def create_pattern(pattern: PatternCreate):
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO patterns (name, description, kind)
            VALUES ($1, $2, $3)
            RETURNING id, name, description, kind, created_at, updated_at
            """,
            pattern.name,
            pattern.description,
            pattern.kind
        )
        return dict(row)
# Upda
class PatternUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    kind: str | None = None

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
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $4
            RETURNING id, name, description, kind, created_at, updated_at
            """,
            patch.name,
            patch.description,
            patch.kind,
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
# GET /query/{table}  (Universal table reader)
# -------------------------------------------------------------------------
@app.get("/query/{table}")
async def query_table(table: str, limit: int = 200):
    """
    Generic SQL reader for any table.
    """
    pool = get_pg_pool()

    # Basic sanitization to block SQL injection
    if not table.replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid table name")

    async with pool.acquire() as conn:
        try:
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

            # Basic routing
            if msg.get("type") == "run_rule":
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
