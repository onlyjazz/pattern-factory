from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from services.pitboss_llm_supervisor import Pitboss
import duckdb
import os
import json
import logging
import uvicorn
from contextlib import contextmanager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app setup
app = FastAPI()

# Allow frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Replace with your frontend origin if different
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@contextmanager
def get_db_connection():
    db_path = os.getenv("DATABASE_LOCATION")
    if not db_path:
        raise RuntimeError("DATABASE_LOCATION environment variable not set")
    conn = duckdb.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connected")

    db = None
    try:
        # Wait for 1 message from client
        data = await websocket.receive_text()
        logger.info(f"Received: {data}")

        # Expecting JSON string with rule_code, system_prompt, protocol_id, and rule_id
        message = json.loads(data)

        # Extract parameters from message
        rule_code = message.get("rule_code")
        system_prompt = message.get("system_prompt")
        protocol_id = message.get("protocol_id")
        rule_id = message.get("rule_id")
        dsl = message.get("dsl")  # For workflow execution

        # Connect to DuckDB
        with get_db_connection() as db:
            pitboss = Pitboss(db, websocket)
            
            # Check if this is a workflow execution
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
                return

    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except Exception as send_err:
            logger.warning(f"Failed to send error over websocket: {send_err}")

    finally:
        try:
            await websocket.close()
        except:
            pass
        logger.info("WebSocket closed")

if __name__ == "__main__":
    logger.info("Starting Pitboss WebSocket server on port 8002")
    uvicorn.run("services.server:app", host="127.0.0.1", port=8002, log_level="info")
