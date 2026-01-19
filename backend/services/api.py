"""
services/api.py
Clean and production-ready Pattern Factory API (Postgres + Pitboss).
"""

import os
import json
import logging
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
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
from backend.pitboss.supervisor import PitbossSupervisor
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

# -------------------------------------------------------------------------
# GET /patterns/search (MUST come before /patterns/{pattern_id})
# -------------------------------------------------------------------------
@app.get("/patterns/search", tags=["Patterns"])
async def search_patterns(q: str = Query("")):
    """Search patterns by name or description for autocomplete."""
    pool = get_pg_pool()
    search_term = f"%{q}%"
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, description, kind
            FROM patterns
            WHERE name ILIKE $1 OR description ILIKE $1
            ORDER BY name ASC
            LIMIT 50
        """, search_term)
    return [dict(r) for r in rows]

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
# Cards CRUD
# -------------------------------------------------------------------------
class CardCreate(BaseModel):
    name: str
    description: str
    pattern_id: int
    markdown: str | None = None
    order_index: int | None = 0
    domain: str | None = None
    audience: str | None = None
    maturity: str | None = None

class CardUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    pattern_id: int | None = None
    markdown: str | None = None
    order_index: int | None = None
    domain: str | None = None
    audience: str | None = None
    maturity: str | None = None

@app.get("/cards", tags=["Cards"])
async def get_cards():
    """Get all cards with pattern information."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT 
                c.id, c.name, c.description, c.markdown, c.order_index, 
                c.domain, c.audience, c.maturity, c.pattern_id, 
                c.created_at, c.updated_at,
                p.name as pattern_name
            FROM cards c
            LEFT JOIN patterns p ON c.pattern_id = p.id
            ORDER BY c.created_at DESC
        """)
    return [dict(r) for r in rows]

@app.post("/cards", tags=["Cards"])
async def create_card(card: CardCreate):
    """Create a new card."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        # Verify pattern exists
        pattern_exists = await conn.fetchval(
            "SELECT id FROM patterns WHERE id = $1", card.pattern_id
        )
        if not pattern_exists:
            raise HTTPException(status_code=400, detail="Pattern not found")
        
        row = await conn.fetchrow(
            """
            INSERT INTO cards (name, description, pattern_id, markdown, order_index, domain, audience, maturity)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id, name, description, markdown, order_index, domain, audience, maturity, pattern_id, created_at, updated_at
            """,
            card.name,
            card.description,
            card.pattern_id,
            card.markdown,
            card.order_index,
            card.domain,
            card.audience,
            card.maturity
        )
        return dict(row)

@app.get("/cards/{card_id}", tags=["Cards"])
async def get_card(card_id: str):
    """Get a single card."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, description, markdown, order_index, domain, audience, maturity, pattern_id, created_at, updated_at
            FROM cards
            WHERE id = $1
            """,
            card_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Card not found")
    return dict(row)

@app.put("/cards/{card_id}", tags=["Cards"])
async def update_card(card_id: str, patch: CardUpdate):
    """Update a card."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        # Verify pattern exists if updating pattern_id
        if patch.pattern_id is not None:
            pattern_exists = await conn.fetchval(
                "SELECT id FROM patterns WHERE id = $1", patch.pattern_id
            )
            if not pattern_exists:
                raise HTTPException(status_code=400, detail="Pattern not found")
        
        row = await conn.fetchrow(
            """
            UPDATE cards
            SET 
                name = COALESCE($1, name),
                description = COALESCE($2, description),
                pattern_id = COALESCE($3, pattern_id),
                markdown = COALESCE($4, markdown),
                order_index = COALESCE($5, order_index),
                domain = COALESCE($6, domain),
                audience = COALESCE($7, audience),
                maturity = COALESCE($8, maturity),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $9
            RETURNING id, name, description, markdown, order_index, domain, audience, maturity, pattern_id, created_at, updated_at
            """,
            patch.name,
            patch.description,
            patch.pattern_id,
            patch.markdown,
            patch.order_index,
            patch.domain,
            patch.audience,
            patch.maturity,
            card_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Card not found")
        return dict(row)

@app.delete("/cards/{card_id}", tags=["Cards"])
async def delete_card(card_id: str):
    """Delete a card."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM cards WHERE id = $1", card_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Card not found")
    return {"status": "ok", "deleted_id": card_id}

@app.get("/patterns/{pattern_id}/cards", tags=["Cards"])
async def get_pattern_cards(pattern_id: int):
    """Get all cards for a specific pattern."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, description, markdown, order_index, domain, audience, maturity, pattern_id, created_at, updated_at
            FROM cards
            WHERE pattern_id = $1
            ORDER BY order_index ASC, created_at DESC
        """, pattern_id)
    return [dict(r) for r in rows]

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
# Threats CRUD
# -------------------------------------------------------------------------
class ThreatCreate(BaseModel):
    name: str
    description: str
    scenario: str | None = None
    probability: int | None = None
    damage_description: str | None = None
    spoofing: bool = False
    tampering: bool = False
    repudiation: bool = False
    information_disclosure: bool = False
    denial_of_service: bool = False
    elevation_of_privilege: bool = False
    mitigation_level: int = 0
    disabled: bool = False
    model_id: int = 1
    card_id: str | None = None

class ThreatUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    scenario: str | None = None
    probability: int | None = None
    damage_description: str | None = None
    spoofing: bool | None = None
    tampering: bool | None = None
    repudiation: bool | None = None
    information_disclosure: bool | None = None
    denial_of_service: bool | None = None
    elevation_of_privilege: bool | None = None
    mitigation_level: int | None = None
    disabled: bool | None = None
    card_id: str | None = None

@app.get("/threats", tags=["Threats"])
async def get_threats():
    """Get all threats for the active model."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, description, scenario, probability, damage_description,
                   spoofing, tampering, repudiation, information_disclosure, 
                   denial_of_service, elevation_of_privilege, mitigation_level, 
                   disabled, model_id, created_at, updated_at
            FROM threat.vthreats
            ORDER BY created_at DESC
        """)
    return [dict(r) for r in rows]

@app.post("/threats", tags=["Threats"])
async def create_threat(threat: ThreatCreate):
    """Create a new threat with optional card association."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO threat.threats 
            (name, description, scenario, probability, damage_description,
             spoofing, tampering, repudiation, information_disclosure,
             denial_of_service, elevation_of_privilege, mitigation_level, disabled, model_id, card_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            RETURNING id, name, description, scenario, probability, damage_description,
                      spoofing, tampering, repudiation, information_disclosure,
                      denial_of_service, elevation_of_privilege, mitigation_level,
                      disabled, model_id, card_id, created_at, updated_at
            """,
            threat.name,
            threat.description,
            threat.scenario,
            threat.probability,
            threat.damage_description,
            threat.spoofing,
            threat.tampering,
            threat.repudiation,
            threat.information_disclosure,
            threat.denial_of_service,
            threat.elevation_of_privilege,
            threat.mitigation_level,
            threat.disabled,
            threat.model_id,
            threat.card_id
        )
        
        return dict(row)

@app.get("/threats/search", tags=["Threats"])
async def search_threats(q: str = Query("")):
    """Search threats by name or description."""
    pool = get_pg_pool()
    search_term = f"%{q}%"
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, description, probability, mitigation_level
            FROM threat.threats
            WHERE name ILIKE $1 OR description ILIKE $1
            ORDER BY name ASC
            LIMIT 50
        """, search_term)
    return [dict(r) for r in rows]

@app.get("/threats/{threat_id}", tags=["Threats"])
async def get_threat(threat_id: int):
    """Get a single threat with optional card details."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, description, scenario, probability, damage_description,
                   spoofing, tampering, repudiation, information_disclosure,
                   denial_of_service, elevation_of_privilege, mitigation_level,
                   disabled, model_id, card_id, created_at, updated_at
            FROM threat.threats
            WHERE id = $1
            """,
            threat_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Threat not found")
        
        threat_dict = dict(row)
        
        # Fetch card details if card_id is present
        if threat_dict.get('card_id'):
            card_row = await conn.fetchrow(
                """
                SELECT id, name, description, markdown, order_index,
                       domain, audience, maturity, pattern_id
                FROM public.cards
                WHERE id = $1
                """,
                threat_dict['card_id']
            )
            threat_dict['card'] = dict(card_row) if card_row else None
        
        return threat_dict

@app.put("/threats/{threat_id}", tags=["Threats"])
async def update_threat(threat_id: int, patch: ThreatUpdate):
    """Update a threat and optionally update associated cards."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        updates = []
        params = []
        param_count = 1
        
        if patch.name is not None:
            updates.append(f"name = ${param_count}")
            params.append(patch.name)
            param_count += 1
        if patch.description is not None:
            updates.append(f"description = ${param_count}")
            params.append(patch.description)
            param_count += 1
        if patch.scenario is not None:
            updates.append(f"scenario = ${param_count}")
            params.append(patch.scenario)
            param_count += 1
        if patch.probability is not None:
            updates.append(f"probability = ${param_count}")
            params.append(patch.probability)
            param_count += 1
        if patch.damage_description is not None:
            updates.append(f"damage_description = ${param_count}")
            params.append(patch.damage_description)
            param_count += 1
        if patch.spoofing is not None:
            updates.append(f"spoofing = ${param_count}")
            params.append(patch.spoofing)
            param_count += 1
        if patch.tampering is not None:
            updates.append(f"tampering = ${param_count}")
            params.append(patch.tampering)
            param_count += 1
        if patch.repudiation is not None:
            updates.append(f"repudiation = ${param_count}")
            params.append(patch.repudiation)
            param_count += 1
        if patch.information_disclosure is not None:
            updates.append(f"information_disclosure = ${param_count}")
            params.append(patch.information_disclosure)
            param_count += 1
        if patch.denial_of_service is not None:
            updates.append(f"denial_of_service = ${param_count}")
            params.append(patch.denial_of_service)
            param_count += 1
        if patch.elevation_of_privilege is not None:
            updates.append(f"elevation_of_privilege = ${param_count}")
            params.append(patch.elevation_of_privilege)
            param_count += 1
        if patch.mitigation_level is not None:
            updates.append(f"mitigation_level = ${param_count}")
            params.append(patch.mitigation_level)
            param_count += 1
        if patch.disabled is not None:
            updates.append(f"disabled = ${param_count}")
            params.append(patch.disabled)
            param_count += 1
        if patch.card_id is not None:
            updates.append(f"card_id = ${param_count}")
            params.append(patch.card_id)
            param_count += 1
        
        # Always update timestamp
        updates.append(f"updated_at = CURRENT_TIMESTAMP")
        params.append(threat_id)
        
        # Build and execute update query
        query = f"""UPDATE threat.threats
                   SET {', '.join(updates)}
                   WHERE id = ${param_count}
                   RETURNING id, name, description, scenario, probability, damage_description,
                             spoofing, tampering, repudiation, information_disclosure,
                             denial_of_service, elevation_of_privilege, mitigation_level,
                             disabled, model_id, card_id, created_at, updated_at"""
        row = await conn.fetchrow(query, *params)
        
        if not row:
            raise HTTPException(status_code=404, detail="Threat not found")
        
        threat_dict = dict(row)
        
        return threat_dict

@app.delete("/threats/{threat_id}", tags=["Threats"])
async def delete_threat(threat_id: int):
    """Delete a threat."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM threat.threats WHERE id = $1", threat_id
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Threat not found")
    return {"status": "ok", "deleted_id": threat_id}

# =========================================================================
# STUB: Current logged-in user (replace with session management)
# =========================================================================
CURRENT_USER_ID = "4da53331-d976-4512-a215-ed756612a8e0"

# -------------------------------------------------------------------------
# Models CRUD
# -------------------------------------------------------------------------
class ModelCreate(BaseModel):
    name: str
    version: str | None = None
    author: str | None = None
    company: str | None = None
    category: str | None = None
    keywords: str | None = None
    description: str | None = None

class ModelUpdate(BaseModel):
    name: str | None = None
    version: str | None = None
    author: str | None = None
    company: str | None = None
    category: str | None = None
    keywords: str | None = None
    description: str | None = None

@app.get("/models", tags=["Models"])
async def get_models():
    """Get all models."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, version, author, company, category, keywords, description, created_at, updated_at
            FROM threat.models
            ORDER BY created_at DESC
        """)
    return [dict(r) for r in rows]

@app.post("/models", tags=["Models"])
async def create_model(model: ModelCreate):
    """Create a new model."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO threat.models (name, version, author, company, category, keywords, description)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, name, version, author, company, category, keywords, description, created_at, updated_at
            """,
            model.name,
            model.version,
            model.author,
            model.company,
            model.category,
            model.keywords,
            model.description
        )
        return dict(row)

@app.get("/models/{model_id}", tags=["Models"])
async def get_model(model_id: int):
    """Get a single model."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, version, author, company, category, keywords, description, created_at, updated_at FROM threat.models WHERE id = $1",
            model_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Model not found")
    return dict(row)

@app.put("/models/{model_id}", tags=["Models"])
async def update_model(model_id: int, patch: ModelUpdate):
    """Update a model."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE threat.models
            SET 
                name = COALESCE($1, name),
                version = COALESCE($2, version),
                author = COALESCE($3, author),
                company = COALESCE($4, company),
                category = COALESCE($5, category),
                keywords = COALESCE($6, keywords),
                description = COALESCE($7, description)
            WHERE id = $8
            RETURNING id, name, version, author, company, category, keywords, description, created_at, updated_at
            """,
            patch.name,
            patch.version,
            patch.author,
            patch.company,
            patch.category,
            patch.keywords,
            patch.description,
            model_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Model not found")
        return dict(row)

@app.delete("/models/{model_id}", tags=["Models"])
async def delete_model(model_id: int):
    """Delete a model."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM threat.models WHERE id = $1", model_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Model not found")
    return {"status": "ok", "deleted_id": model_id}

@app.post("/models/{model_id}/activate", tags=["Models"])
async def activate_model(model_id: int):
    """Set model as active for the current user."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        # Verify model exists
        model_exists = await conn.fetchval(
            "SELECT id FROM threat.models WHERE id = $1", model_id
        )
        if not model_exists:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Get user (stub user for now)
        user_id = CURRENT_USER_ID
        user_exists = await conn.fetchval(
            "SELECT id FROM public.users WHERE id = $1", user_id
        )
        if not user_exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Upsert: insert new active model or update if user already has one
        await conn.execute(
            """
            INSERT INTO public.active_models (user_id, model_id) 
            VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE 
            SET model_id = $2, updated_at = CURRENT_TIMESTAMP
            """,
            user_id,
            model_id
        )
    return {"status": "ok", "user_id": user_id, "model_id": model_id}

@app.get("/active-model", tags=["Models"])
async def get_active_model():
    """Get the active model for the current user."""
    pool = get_pg_pool()
    user_id = CURRENT_USER_ID
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT model_id FROM public.active_models WHERE user_id = $1",
            user_id
        )
    if not row:
        return {"model_id": None}
    return {"model_id": row["model_id"]}

# -------------------------------------------------------------------------
# Assets CRUD
# -------------------------------------------------------------------------
class AssetCreate(BaseModel):
    name: str
    description: str
    fixed_value: float = 0
    disabled: bool = False
    model_id: int = 1

class AssetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    fixed_value: float | None = None
    disabled: bool | None = None

@app.get("/assets", tags=["Assets"])
async def get_assets():
    """Get all assets for the active model."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, description, fixed_value, disabled, model_id, created_at, updated_at
            FROM threat.vassets
            ORDER BY created_at DESC
        """)
    return [dict(r) for r in rows]

@app.post("/assets", tags=["Assets"])
async def create_asset(asset: AssetCreate):
    """Create a new asset."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO threat.assets (name, description, fixed_value, disabled, model_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, name, description, fixed_value, disabled, model_id, created_at, updated_at
            """,
            asset.name,
            asset.description,
            asset.fixed_value,
            asset.disabled,
            asset.model_id
        )
        return dict(row)

@app.get("/assets/{asset_id}", tags=["Assets"])
async def get_asset(asset_id: int):
    """Get a single asset."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, description, fixed_value, disabled, model_id, created_at, updated_at FROM threat.assets WHERE id = $1",
            asset_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    return dict(row)

@app.put("/assets/{asset_id}", tags=["Assets"])
async def update_asset(asset_id: int, patch: AssetUpdate):
    """Update an asset."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE threat.assets
            SET 
                name = COALESCE($1, name),
                description = COALESCE($2, description),
                fixed_value = COALESCE($3, fixed_value),
                disabled = COALESCE($4, disabled)
            WHERE id = $5
            RETURNING id, name, description, fixed_value, disabled, model_id, created_at, updated_at
            """,
            patch.name,
            patch.description,
            patch.fixed_value,
            patch.disabled,
            asset_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Asset not found")
        return dict(row)

@app.delete("/assets/{asset_id}", tags=["Assets"])
async def delete_asset(asset_id: int):
    """Delete an asset."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM threat.assets WHERE id = $1", asset_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Asset not found")
    return {"status": "ok", "deleted_id": asset_id}

# -------------------------------------------------------------------------
# Vulnerabilities CRUD
# -------------------------------------------------------------------------
class VulnerabilityCreate(BaseModel):
    name: str
    description: str
    disabled: bool = False
    model_id: int = 1

class VulnerabilityUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    disabled: bool | None = None

@app.get("/vulnerabilities", tags=["Vulnerabilities"])
async def get_vulnerabilities():
    """Get all vulnerabilities for the active model."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, description, disabled, model_id, created_at, updated_at
            FROM threat.vvulnerabilities
            ORDER BY created_at DESC
        """)
    return [dict(r) for r in rows]

@app.post("/vulnerabilities", tags=["Vulnerabilities"])
async def create_vulnerability(vulnerability: VulnerabilityCreate):
    """Create a new vulnerability."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO threat.vulnerabilities (name, description, disabled, model_id)
            VALUES ($1, $2, $3, $4)
            RETURNING id, name, description, disabled, model_id, created_at, updated_at
            """,
            vulnerability.name,
            vulnerability.description,
            vulnerability.disabled,
            vulnerability.model_id
        )
        return dict(row)

@app.get("/vulnerabilities/{vulnerability_id}", tags=["Vulnerabilities"])
async def get_vulnerability(vulnerability_id: int):
    """Get a single vulnerability."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, description, disabled, model_id, created_at, updated_at FROM threat.vulnerabilities WHERE id = $1",
            vulnerability_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    return dict(row)

@app.put("/vulnerabilities/{vulnerability_id}", tags=["Vulnerabilities"])
async def update_vulnerability(vulnerability_id: int, patch: VulnerabilityUpdate):
    """Update a vulnerability."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE threat.vulnerabilities
            SET 
                name = COALESCE($1, name),
                description = COALESCE($2, description),
                disabled = COALESCE($3, disabled)
            WHERE id = $4
            RETURNING id, name, description, disabled, model_id, created_at, updated_at
            """,
            patch.name,
            patch.description,
            patch.disabled,
            vulnerability_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Vulnerability not found")
        return dict(row)

@app.delete("/vulnerabilities/{vulnerability_id}", tags=["Vulnerabilities"])
async def delete_vulnerability(vulnerability_id: int):
    """Delete a vulnerability."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM threat.vulnerabilities WHERE id = $1", vulnerability_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Vulnerability not found")
    return {"status": "ok", "deleted_id": vulnerability_id}

# -------------------------------------------------------------------------
# Countermeasures CRUD
# -------------------------------------------------------------------------
class CountermeasureCreate(BaseModel):
    name: str
    description: str
    fixed_implementation_cost: int = 0
    disabled: bool = False
    model_id: int = 1

class CountermeasureUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    fixed_implementation_cost: int | None = None
    disabled: bool | None = None

@app.get("/countermeasures", tags=["Countermeasures"])
async def get_countermeasures():
    """Get all countermeasures for the active model."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, name, description, fixed_implementation_cost, disabled, model_id, created_at, updated_at
            FROM threat.vcountermeasures
            ORDER BY created_at DESC
        """)
    return [dict(r) for r in rows]

@app.post("/countermeasures", tags=["Countermeasures"])
async def create_countermeasure(countermeasure: CountermeasureCreate):
    """Create a new countermeasure."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO threat.countermeasures (name, description, fixed_implementation_cost, disabled, model_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, name, description, fixed_implementation_cost, disabled, model_id, created_at, updated_at
            """,
            countermeasure.name,
            countermeasure.description,
            countermeasure.fixed_implementation_cost,
            countermeasure.disabled,
            countermeasure.model_id
        )
        return dict(row)

@app.get("/countermeasures/{countermeasure_id}", tags=["Countermeasures"])
async def get_countermeasure(countermeasure_id: int):
    """Get a single countermeasure."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, description, fixed_implementation_cost, disabled, model_id, created_at, updated_at FROM threat.countermeasures WHERE id = $1",
            countermeasure_id
        )
    if not row:
        raise HTTPException(status_code=404, detail="Countermeasure not found")
    return dict(row)

@app.put("/countermeasures/{countermeasure_id}", tags=["Countermeasures"])
async def update_countermeasure(countermeasure_id: int, patch: CountermeasureUpdate):
    """Update a countermeasure."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE threat.countermeasures
            SET 
                name = COALESCE($1, name),
                description = COALESCE($2, description),
                fixed_implementation_cost = COALESCE($3, fixed_implementation_cost),
                disabled = COALESCE($4, disabled)
            WHERE id = $5
            RETURNING id, name, description, fixed_implementation_cost, disabled, model_id, created_at, updated_at
            """,
            patch.name,
            patch.description,
            patch.fixed_implementation_cost,
            patch.disabled,
            countermeasure_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Countermeasure not found")
        return dict(row)

@app.delete("/countermeasures/{countermeasure_id}", tags=["Countermeasures"])
async def delete_countermeasure(countermeasure_id: int):
    """Delete a countermeasure."""
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM threat.countermeasures WHERE id = $1", countermeasure_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Countermeasure not found")
    return {"status": "ok", "deleted_id": countermeasure_id}

# -------------------------------------------------------------------------
# GET /views  (Mode-aware view registry)
# -------------------------------------------------------------------------
@app.get("/views")
async def get_views(mode: str = 'explore', limit: int = 200):
    """
    Get views filtered by mode.
    
    Parameters:
        mode: 'explore' or 'model' (default: 'explore')
        limit: Maximum number of views to return (default: 200)
    
    Returns list of views from views_registry where mode matches the requested mode.
    """
    if mode not in ['explore', 'model']:
        raise HTTPException(status_code=400, detail="Invalid mode. Must be 'explore' or 'model'")
    
    pool = get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, table_name, mode, created_at, updated_at
            FROM public.views_registry
            WHERE mode = $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            mode,
            limit
        )
    return [dict(r) for r in rows]

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
