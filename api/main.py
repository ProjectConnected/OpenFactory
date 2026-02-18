import os
import sqlite3
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

DB_PATH = os.getenv("OPENFACTORY_DB_PATH", "/data/openfactory.db")
API_KEY_FILE = os.getenv("OPENFACTORY_API_KEY_FILE", "/secrets/openfactory_api_key.txt")

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY,
          status TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          pr_url TEXT,
          ci_status TEXT,
          error TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

def check_api_key(key: str | None):
    try:
        with open(API_KEY_FILE, "r", encoding="utf-8") as f:
            expected = f.read().strip()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="api key file missing")
    if not key or key != expected:
        raise HTTPException(status_code=401, detail="unauthorized")

class JobCreate(BaseModel):
    owner: str
    repo: str
    task: str
    private: bool = True
    template: str = "python-fastapi"

app = FastAPI()

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/health")
def health():
    init_db()
    return {"ok": True}

@app.post("/v1/jobs")
def create_job(payload: JobCreate, x_openfactory_key: str | None = Header(default=None)):
    check_api_key(x_openfactory_key)
    jid = str(uuid.uuid4())
    ts = now_iso()
    import json
    conn = get_conn()
    conn.execute(
        "INSERT INTO jobs (id,status,payload_json,created_at,updated_at) VALUES (?,?,?,?,?)",
        (jid, "queued", json.dumps(payload.model_dump()), ts, ts),
    )
    conn.commit()
    conn.close()
    return {"id": jid, "status": "queued"}

@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str, x_openfactory_key: str | None = Header(default=None)):
    check_api_key(x_openfactory_key)
    conn = get_conn()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return {
        "id": row["id"],
        "status": row["status"],
        "pr_url": row["pr_url"],
        "ci_status": row["ci_status"],
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
