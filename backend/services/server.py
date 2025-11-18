from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pitboss.supervisor import Pitboss
import psycopg
import os
import json
import logging
import uvicorn
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@contextmanager
def get_db_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    conn = psycopg.connect(db_url)
    try:
        yield conn
    finally:
        conn.close()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected")

    try:
        data = await websocket.receive_text()
        message = json.loads(data)

        rule_code = message.get("rule_code")
        system_prompt = message.get("system_prompt")
        protocol_id = message.get("protocol_id")
        rule_id = message.get("rule_id")
        dsl = message.get("dsl")

        with get_db_connection() as db:
            pitboss = Pitboss(db, websocket)

            if dsl:
                logger.info("Processing DSL workflow...")
                await pitboss.run_workflow(dsl)

            elif rule_code:
                logger.info("Processing single rule...")
                await pitboss.process_rule_request(
                    rule_code=rule_code,
                    system_prompt=system_prompt,
                    protocol_id=protocol_id,
                    rule_id=rule_id
                )
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "Missing 'rule_code' or 'dsl'"
                })

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e),
                "error_type": e.__class__.__name__
            })
        except:
            pass

    finally:
        await websocket.close()
        logger.info("WebSocket closed")

if __name__ == "__main__":
    logger.info("Starting Pitboss WebSocket server on port 8002")
    uvicorn.run("services.server:app", host="127.0.0.1", port=8002, log_level="info")
