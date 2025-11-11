from fastapi import FastAPI, HTTPException, UploadFile, File, Form, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
import duckdb
from dotenv import load_dotenv
import os
from datetime import datetime
import yaml
from pathlib import Path
from services.pitboss import Pitboss
import json
import uvicorn
import logging
from contextlib import contextmanager


load_dotenv()
DATABASE_LOCATION = os.getenv("DATABASE_LOCATION")

# ✅ Shared DuckDB connection and lock
import threading
duckdb_conn = duckdb.connect(DATABASE_LOCATION, read_only=False)
duckdb_lock = threading.Lock()
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
    
app = FastAPI(
    title="DB Column Extraction API",
    description="API for accessing clinical trial data from the DDT table",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DDTItemSummary(BaseModel):
    item_id: str
    description: str

    model_config = ConfigDict(from_attributes=True)

class DDT(BaseModel):
    crf: str
    item_id: str
    description: str
    comments: str
    protocol_id: str

class SelectData(BaseModel):
    subjid: str
    lbtest: str
    lbstresn: float
    lbstunit: str
    visitdy: int
    visit: str

    model_config = ConfigDict(from_attributes=True)

class Protocol(BaseModel):
    protocol_id: str
    description: str
    date_created: datetime
    date_amended: datetime
    sponsor: str

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

class Alert(BaseModel):
    subjid: str
    protocol_id: str
    crf: str
    variable: str
    rule_id: str
    status: int

    model_config = ConfigDict(from_attributes=True)

class Rule(BaseModel):
    rule_id: str
    protocol_id: str
    sponsor: str
    rule_code: str
    date_created: datetime
    date_amended: datetime

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

class Data(BaseModel):
    crf: str
    protocol_id: str
    data: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)

class Workflow(BaseModel):
    workflow_id: str
    protocol_id: str
    sponsor: str
    workflow_code: str
    date_created: datetime
    date_amended: datetime

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

# Connect to DuckDB
print("connecting")
conn = duckdb_conn, read_only=True)
print("connected")

@app.get("/", tags=["Root"])
def root():
    return {"message": "API root - use /read_ddt_items to get items"}

@app.get("/read_ddt_items", tags=["DDT Items"])
def read_ddt_items():
    print("reading")
    try:
        results = conn.execute("SELECT item_id, description FROM ddt").fetchall()
        print(results)
        return [DDTItemSummary(item_id=r[0], description=r[1]) for r in results]
    except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload_protocol", tags=["Protocol Management"])
async def upload_protocol(
    protocol_id: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are allowed"
            )
            
        protocols_dir = Path("protocols")
        protocols_dir.mkdir(exist_ok=True)
        
        file_extension = Path(file.filename).suffix
        file_path = protocols_dir / f"{protocol_id}{file_extension}"
        
        # Save the file
        content = file.file.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        return {
            "message": "Protocol file uploaded successfully",
            "protocol_id": protocol_id,
            "filename": file.filename
        }
        
    except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_ddt", tags=["DDT"])
def get_ddt(protocol_id: str = "20050203"):
     #defaults to 20050203 unless specified otherwise
    try:
        results = conn.execute("SELECT * FROM ddt WHERE protocol_id = ?", (protocol_id,)).fetchall()
        return [DDT(crf=r[0], item_id=r[1], description=r[2], comments=r[3], protocol_id=r[4]) for r in results]
    except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_ddt", tags=["Add DDT"])
def add_ddt(ddt: DDT):
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS ddt (crf TEXT, item_id TEXT, description TEXT, comments TEXT, protocol_id TEXT)")
        conn.execute("INSERT INTO ddt (crf, item_id, description, comments, protocol_id) VALUES (?, ?, ?, ?, ?)", 
                    (ddt.crf, ddt.item_id, ddt.description, ddt.comments, ddt.protocol_id))
    except duckdb.DataError as db_error:
        raise HTTPException(status_code=400, detail=f"Database error: {str(db_error)}")
    except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_data", tags=["Data"])
def get_data(crf: str = "ADLB_PDS2019", protocol_id: str = "20050203"):
    #defaults to ADLB_PDS2019 and 20050203 unless specified otherwise
    try:
        # Define CRF to table mapping
        crf_to_table = {
            "ADLB_PDS2019": "adlb_pds2019",
            "ADAE_PDS2019": "adae_pds2019",
            "ADLS_PDS2019": "adls_pds2019",
            "ADPM_PDS2019": "adpm_pds2019",
            "ADRS_PDS2019": "adrsp_pds2019",
            "ADSL_PDS2019": "adsl_pds2019",
            "BIOMARK_PDS2019": "biomark_pds2019"
        }
        
        # Get the table name from CRF
        table_name = crf_to_table.get(crf.upper())
        if not table_name:
            raise HTTPException(status_code=400, detail=f"Invalid CRF: {crf}")
            
        # Build and execute the query
        query = f"SELECT * FROM {table_name} WHERE protocol_id = ?"
        results = conn.execute(query, (protocol_id,)).fetchall()
        
        return results
        
    except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_data", tags=["Data Management"])
def add_data(data: Data):
    try:
        crf_to_table = {
            "ADLB_PDS2019": "adlb_pds2019",
            "ADAE_PDS2019": "adae_pds2019",
            "ADLS_PDS2019": "adls_pds2019",
            "ADPM_PDS2019": "adpm_pds2019",
            "ADRS_PDS2019": "adrsp_pds2019",
            "ADSL_PDS2019": "adsl_pds2019",
            "BIOMARK_PDS2019": "biomark_pds2019"
        }
        
        table_name = crf_to_table.get(data.crf.upper())
        if not table_name:
            raise HTTPException(status_code=400, detail=f"Invalid CRF: {data.crf}")
            
        columns_info = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        column_names = [row[1] for row in columns_info] 

        missing_columns = [col for col in column_names if col not in data.data]
        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
            
        # Build the SQL query dynamically
        columns_str = ', '.join(data.data.keys())
        values_str = ', '.join(['?'] * len(data.data))
        
        # Get values in the correct order
        values = [data.data[col] for col in column_names]
        
        # Insert the data, need to add create table if not exists functionality
        conn.execute(f"INSERT INTO {table_name} ({columns_str}) VALUES ({values_str})", values)
        
        return {
            "message": "Data added successfully",
            "crf": data.crf,
            "protocol_id": data.protocol_id,
            "table": table_name
        }
        
    except duckdb.DataError as db_error:
        raise HTTPException(status_code=400, detail=f"Database error: {str(db_error)}")
    except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))
        

@app.get("/execute_rule", tags=["Rule Execution"])
def execute_rule(protocol_id: str = "20050203", lbtest: str = "Albumin", lbstresn_min: float = 100):
    print("selecting")
    try:
        query = """SELECT subjid, lbtest, lbstresn, lbstunit, visitdy, visit FROM adlb_pds2019 
        WHERE protocol_id = ? AND lbtest = ? AND lbstresn >= ?"""

        with duckdb_lock:
            results = with duckdb_lock:
    duckdb_conn.execute(query, (protocol_id, lbtest, lbstresn_min)).fetchall()
            print(lbtest)
            for result in results:
                conn.execute("INSERT OR IGNORE INTO alerts (subjid, protocol_id, crf, variable, rule_id, status) VALUES (?, ?, ?, ?, ?, ?)", (result[0], protocol_id, "ADLB_PDS2019", lbtest, "lbstresn_min100", 1))
                print("inserted")
        return [SelectData(subjid=result[0], lbtest=result[1], lbstresn=float(result[2]), lbstunit=result[3], visitdy=int(result[4]), visit=result[5]) for result in results]
    except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_protocols", tags=["Retrieve protocol"])
def get_protocols():
    try:
        results = conn.execute("SELECT * FROM protocols").fetchall()
        return [Protocol(protocol_id=r[0], description=r[1], date_created=r[2], date_amended=r[3], sponsor=r[4]) for r in results]
    except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_protocol", tags=["Add protocol"])
def add_protocol(protocol: Protocol):
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS protocols (protocol_id TEXT PRIMARY KEY, description TEXT, date_created TIMESTAMP, date_amended TIMESTAMP, sponsor TEXT)")
        conn.execute("INSERT INTO protocols (protocol_id, description, date_created, date_amended, sponsor) VALUES (?, ?, ?, ?, ?)", 
                    (protocol.protocol_id, protocol.description, protocol.date_created.isoformat(), protocol.date_amended.isoformat(), protocol.sponsor))
    except duckdb.DataError as db_error:
        raise HTTPException(status_code=400, detail=f"Database error: {str(db_error)}")
    except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_alerts", tags=["Retrieve alerts"])
def get_alerts():
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS alerts (subjid TEXT, protocol_id TEXT, crf TEXT, variable TEXT, rule_id TEXT, status INTEGER, UNIQUE(subjid, rule_id, protocol_id));")
        results = conn.execute("SELECT * FROM alerts").fetchall()
        return [Alert(subjid=r[0], protocol_id=r[1], crf=r[2], variable=r[3], rule_id=r[4], status=r[5]) for r in results]
    except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_alert", tags=["Add alert"])
def add_alert(alert: Alert):
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS alerts (subjid TEXT, protocol_id TEXT, crf TEXT, variable TEXT, rule_id TEXT, status INTEGER, UNIQUE(subjid, rule_id, protocol_id));")
        conn.execute("INSERT INTO alerts (subjid, protocol_id, crf, variable, rule_id, status) VALUES (?, ?, ?, ?, ?, ?)", 
                    (alert.subjid, alert.protocol_id, alert.crf, alert.variable, alert.rule_id, alert.status))
    except duckdb.DataError as db_error:
        raise HTTPException(status_code=400, detail=f"Database error: {str(db_error)}")
    except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_rules", tags=["Retrieve rules"])
def get_rules():
    try:
        results = conn.execute("SELECT * FROM rules").fetchall()
        return [Rule(rule_id=r[0], protocol_id=r[1], sponsor=r[2], rule_code=r[3], date_created=r[4], date_amended=r[5]) for r in results]
    except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_rule", tags=["Insert rule"])
def add_rule(rule: Rule):
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS rules (rule_id TEXT PRIMARY KEY, protocol_id TEXT, sponsor TEXT, rule_code TEXT, date_created TIMESTAMP, date_amended TIMESTAMP)")
        conn.execute("INSERT OR IGNORE INTO rules (rule_id, protocol_id, sponsor, rule_code, date_created, date_amended) VALUES (?, ?, ?, ?, ?, ?)", 
                    (rule.rule_id, rule.protocol_id, rule.sponsor, rule.rule_code, rule.date_created.isoformat(), rule.date_amended.isoformat()))
    
    except duckdb.DataError as db_error:
        raise HTTPException(status_code=400, detail=f"Database error: {str(db_error)}")
    except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))

@app.post("/save_workflow", tags=["Workflow Management"])
def save_workflow(workflow: Workflow):
    try:
        return {
            "status": "success",
            "message": "Stub endpoint received request successfully",
            "received_data": body
        }
    except Exception as e:
    import traceback
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))


@contextmanager
def get_db_connection():
    db_path = os.getenv("DATABASE_LOCATION")
    if not db_path:
        raise RuntimeError("DATABASE_LOCATION environment variable not set")
    conn = duckdb_conn
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

        # Expecting JSON string with optional "system_prompt"
        message = json.loads(data)

        # Hardcoded rule for now
        rule_code = "Find all patients with albumin levels above 100"
        system_prompt = message.get("system_prompt")  # optional

        if not rule_code:
            await websocket.send_json({
                "type": "error",
                "message": "Missing 'rule_code'"
            })
            return

        # Connect to DuckDB and process the rule
        with get_db_connection() as db:
            pitboss = Pitboss(db, websocket)
            await pitboss.process_rule_request(websocket, rule_code, system_prompt)

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

# if __name__ == "__main__":
#     logger.info("🚀 Starting WebSocket server on port 8002")
#     uvicorn.run("api:app", host="127.0.0.1", port=8000, log_level="info")
