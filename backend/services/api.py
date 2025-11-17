"""
services/api.py — Stable Postgres Version (Nov 2025)
---------------------------------------------------
Centralized Postgres connection management.
Pitboss and all agents call back into this module to get pooled access.
"""

# ──────────────────────────────────────────────
# Logging setup
# ──────────────────────────────────────────────
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("services.api")
logger.info("📦 API module initializing (Postgres mode)")

# ──────────────────────────────────────────────
# Core imports
# ──────────────────────────────────────────────
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any
from pydantic import BaseModel
import os
import json
import asyncio
import asyncpg
from datetime import datetime
from dotenv import load_dotenv
import httpx
from openai import OpenAI

# ──────────────────────────────────────────────
# Load environment
# ──────────────────────────────────────────────
load_dotenv()

# Postgres
PGHOST = os.getenv("PGHOST", "127.0.0.1")
PGPORT = os.getenv("PGPORT", "5432")
PGUSER = os.getenv("PGUSER", "pattern_factory")
PGDATABASE = os.getenv("PGDATABASE", "pattern_factory")
PGPASSWORD = os.getenv("PGPASSWORD", "314159")

POSTGRES_DSN = f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"
PG_POOL: Optional[asyncpg.Pool] = None

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAPI_KEY_BILLING = os.getenv("OPENAPI_KEY_BILLING")

# API config
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))

# ──────────────────────────────────────────────
# FastAPI app initialization
# ──────────────────────────────────────────────
app = FastAPI(
    title="Pattern Factory API",
    description="Central API with Postgres pool and Pitboss supervisor",
    version="2.0.0",
)

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Global accessors
# ──────────────────────────────────────────────
def get_pg_pool() -> Optional[asyncpg.Pool]:
    """Accessor for other modules to retrieve the running Postgres pool."""
    return PG_POOL

# ──────────────────────────────────────────────
# Postgres startup & shutdown
# ──────────────────────────────────────────────
@app.on_event("startup")
async def init_postgres():
    global PG_POOL
    try:
        logger.info(f"🐘 Connecting to Postgres: {POSTGRES_DSN}")
        PG_POOL = await asyncpg.create_pool(dsn=POSTGRES_DSN, min_size=1, max_size=5)
        async with PG_POOL.acquire() as conn:
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS system_log (
                id SERIAL PRIMARY KEY,
                event TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
        logger.info("✅ Connected to Postgres successfully")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Postgres: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_postgres():
    global PG_POOL
    if PG_POOL:
        await PG_POOL.close()
        logger.info("🧹 Closed Postgres connection pool.")

# ──────────────────────────────────────────────
# OpenAI Diagnostics
# ──────────────────────────────────────────────
@app.on_event("startup")
async def openai_diagnostics():
    """Optional diagnostic check for OpenAI connectivity."""
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        models = [m.id for m in client.models.list().data[:3]]
        logger.info(f"🧠 OpenAI models available: {', '.join(models)}")
    except Exception as e:
        logger.warning(f"⚠️ OpenAI diagnostics failed: {e}")

# ──────────────────────────────────────────────
# Import Pitboss after pool creation
# ──────────────────────────────────────────────
try:
    from services.pitboss_research import Pitboss
    logger.info("✅ Imported Pitboss (research version)")
except Exception as e:
    logger.error(f"❌ Could not import Pitboss: {e}")

# ──────────────────────────────────────────────
# Root endpoint
# ──────────────────────────────────────────────
@app.get("/", tags=["Root"])
async def root():
    return {"message": "Pattern Factory API (Postgres mode) operational"}

# ──────────────────────────────────────────────
# WebSocket endpoint
# ──────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 WebSocket connected")

    if PG_POOL is None:
        await websocket.send_json({"type": "error", "message": "Database not connected"})
        await websocket.close()
        return

    # Pass the API service (this module) to Pitboss
    pitboss = Pitboss(api_services=app, websocket=websocket)
    logger.info("🧠 Pitboss instantiated via API service accessor")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            # Basic echo or route to pitboss
            if msg.get("type") == "run_workflow":
                await pitboss.run_pattern_workflow(msg.get("params", {}))
            else:
                await websocket.send_json({"type": "echo", "message": msg})
    except WebSocketDisconnect:
        logger.info("🔌 WebSocket disconnected")
    finally:
        await websocket.close()

# ──────────────────────────────────────────────
# Utility: simple system-log write
# ──────────────────────────────────────────────
@app.post("/log", tags=["System"])
async def write_log(event: str):
    if PG_POOL is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    async with PG_POOL.acquire() as conn:
        await conn.execute("INSERT INTO system_log (event) VALUES ($1)", event)
    return {"status": "ok", "event": event, "timestamp": datetime.now().isoformat()}

# ──────────────────────────────────────────────
# Final readiness banner
# ──────────────────────────────────────────────
logger.info(f"""
==========================================
✅ Pattern Factory API Ready
🐘 Database: {POSTGRES_DSN}
🔑 OpenAI prefix: {OPENAI_API_KEY[:12] if OPENAI_API_KEY else 'MISSING'}
⚙️ Host: {API_HOST}:{API_PORT}
==========================================
""")
