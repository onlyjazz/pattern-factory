"""
services/api.py — Stable version (Oct 2025)
"""

# ──────────────────────────────────────────────
# Logging must come first
# ──────────────────────────────────────────────
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("services.api")
logger.info("📦 API module initializing")

# ──────────────────────────────────────────────
# Core imports
# ──────────────────────────────────────────────
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, ConfigDict
import os
import duckdb
import json
import asyncio
from contextlib import contextmanager
from datetime import datetime
from dotenv import load_dotenv

# ──────────────────────────────────────────────
# Load environment
# ──────────────────────────────────────────────
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAPI_KEY_BILLING = os.getenv("OPENAI_API_KEY_BILLING")
DATABASE_LOCATION = os.getenv("DATABASE_LOCATION")

if not OPENAI_API_KEY:
    logger.warning("⚠️ OPENAI_API_KEY missing from environment")
else:
    logger.info(f"🔑 OPENAI_API_KEY prefix: {OPENAI_API_KEY[:12]}")

if not OPENAI_API_KEY_BILLING:
    logger.warning("⚠️ OPENAI_API_KEY_BILLING missing from environment")
else:
    logger.info(f"🔑 OPENAI_API_KEY_BILLING prefix: {OPENAI_API_KEY_BILLING[:12]}")
# ──────────────────────────────────────────────
# Define FastAPI app early — before any risky ops
# ──────────────────────────────────────────────
app = FastAPI(
    title="DB Column Extraction API",
    description="API for accessing clinical trial data from the DDT table",
    version="1.0.0",
)

# Add CORS middleware here (not inside startup)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Import Pitboss safely
# ──────────────────────────────────────────────
try:
    from services.pitboss_llm_supervisor import Pitboss
    logger.info("✅ Imported Pitboss successfully")
except Exception as e:
    logger.error(f"❌ Failed to import Pitboss: {e}")

# ──────────────────────────────────────────────
# Initialize DuckDB connection
# ──────────────────────────────────────────────
duckdb_lock = asyncio.Lock()
conn = None
if DATABASE_LOCATION:
    try:
        db_path = os.path.expanduser(DATABASE_LOCATION)
        conn = duckdb.connect(db_path)
        logger.info(f"💾 Connected to DuckDB at {db_path}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to DuckDB: {e}")
else:
    logger.warning("⚠️ DATABASE_LOCATION not set in .env")

# ──────────────────────────────────────────────
# Startup diagnostics
# ──────────────────────────────────────────────
import httpx
from openai import OpenAI

@app.on_event("startup")
async def startup_diagnostics():
    """Run diagnostics for OpenAI connectivity."""
    key_prefix = org = project = "N/A"
    models = []
    billing_line = "💳 Billing info unavailable"

    try:
        client = OpenAI()
        key_prefix = client.api_key[:12] if client.api_key else "MISSING"
        org = getattr(client, "organization", None)
        project = getattr(client, "project", None)
        models = [m.id for m in client.models.list().data[:3]]

        billing_headers = {"Authorization": f"Bearer {client.api_key}"}
        async with httpx.AsyncClient(timeout=10.0) as session:
            balance_resp = await session.get(
                "https://api.openai.com/v1/dashboard/billing/credit_grants",
                headers=billing_headers,
            )

        if balance_resp.status_code == 200:
            billing_json = balance_resp.json()
            total_granted = billing_json.get("total_granted", 0)
            total_used = billing_json.get("total_used", 0)
            total_available = billing_json.get("total_available", 0)
            billing_line = (
                f"💳 Credit granted: ${total_granted:.2f} | "
                f"Used: ${total_used:.2f} | Remaining: ${total_available:.2f}"
            )
        elif balance_resp.status_code == 401:
            logger.warning("🔒 Billing data not available for project keys (401 Unauthorized).")
        else:
            logger.warning(f"⚠️ Unexpected billing response: {balance_resp.status_code}")

    except Exception as e:
        logger.error(f"❌ OpenAI diagnostics failed: {e}")

    finally:
        logger.info(f"""
==========================================
🩺 OPENAI STARTUP DIAGNOSTICS
🔑 Key prefix: {key_prefix}
🏢 Org: {org}
📦 Project: {project}
🧠 Models available: {', '.join(models) if models else 'N/A'}
{billing_line}
💾 Database: {DATABASE_LOCATION or 'N/A'}
⚙️ Log level: INFO
==========================================
""")

# ──────────────────────────────────────────────
# Minimal endpoint for test
# ──────────────────────────────────────────────
@app.get("/", tags=["Root"])
def root():
    return {"message": "API root - system operational"}

# ──────────────────────────────────────────────
# WebSocket endpoint (simplified for now)
# ──────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket):
    await websocket.accept()
    logger.info("🔌 WebSocket connected")

    if conn is None:
        await websocket.send_json({"type": "error", "message": "Database not connected"})
        await websocket.close()
        return

    pitboss = Pitboss(conn, websocket)
    logger.info("🧠 Pitboss created and linked to WebSocket")

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            await websocket.send_json({"type": "echo", "message": msg})
    except WebSocketDisconnect:
        logger.info("🔌 WebSocket disconnected")
    finally:
        await websocket.close()

# ──────────────────────────────────────────────
# Final system readiness log
# ──────────────────────────────────────────────
logger.info(f"""
==========================================
✅ System Ready
🔑 OpenAI key prefix: {OPENAI_API_KEY[:12] if OPENAI_API_KEY else 'MISSING'}
💾 Database: {DATABASE_LOCATION or 'N/A'}
⚙️ Logging level: INFO
==========================================
""")
