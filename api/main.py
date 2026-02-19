import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

DB_PATH = os.getenv("OPENFACTORY_DB_PATH", "/data/openfactory.db")
API_KEY_FILE = os.getenv("OPENFACTORY_API_KEY_FILE", "/secrets/openfactory_api_key.txt")
ARTIFACT_ROOT = Path(os.getenv("OPENFACTORY_ARTIFACT_ROOT", "/data/openfactory/jobs"))


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
          trace_id TEXT,
          stage TEXT,
          status TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          model_json TEXT,
          pr_url TEXT,
          ci_status TEXT,
          error TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    for col, ddl in {
        "trace_id": "ALTER TABLE jobs ADD COLUMN trace_id TEXT",
        "model_json": "ALTER TABLE jobs ADD COLUMN model_json TEXT",
        "stage": "ALTER TABLE jobs ADD COLUMN stage TEXT",
    }.items():
        if col not in cols:
            conn.execute(ddl)
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
    trace_id = f"trace-{jid[:8]}"
    ts = now_iso()
    conn = get_conn()
    conn.execute(
        "INSERT INTO jobs (id,trace_id,stage,status,payload_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (jid, trace_id, "queued", "queued", json.dumps(payload.model_dump()), ts, ts),
    )
    conn.commit()
    conn.close()
    return {"id": jid, "trace_id": trace_id, "stage": "queued", "status": "queued"}


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str, x_openfactory_key: str | None = Header(default=None)):
    check_api_key(x_openfactory_key)
    conn = get_conn()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    model_cfg = {}
    if row["model_json"]:
        try:
            model_cfg = json.loads(row["model_json"])
        except Exception:
            model_cfg = {"parse_error": True}
    return {
        "id": row["id"],
        "trace_id": row["trace_id"],
        "stage": row["stage"],
        "status": row["status"],
        "pr_url": row["pr_url"],
        "ci_status": row["ci_status"],
        "error": row["error"],
        "model": model_cfg,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@app.post("/v1/jobs/{job_id}/cancel")
def cancel_job(job_id: str, x_openfactory_key: str | None = Header(default=None)):
    check_api_key(x_openfactory_key)
    conn = get_conn()
    row = conn.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="not found")
    if row["status"] in {"done", "failed", "ci_failed", "cancelled"}:
        conn.close()
        return {"id": job_id, "status": row["status"]}
    conn.execute("UPDATE jobs SET status=?, stage=?, updated_at=? WHERE id=?", ("cancel_requested", "cancel_requested", now_iso(), job_id))
    conn.commit()
    conn.close()
    return {"id": job_id, "status": "cancel_requested"}


@app.get("/v1/jobs/{job_id}/artifacts")
def list_artifacts(job_id: str, x_openfactory_key: str | None = Header(default=None)):
    check_api_key(x_openfactory_key)
    job_dir = ARTIFACT_ROOT / job_id
    files = []
    if job_dir.exists():
        for p in sorted(job_dir.rglob("*")):
            if p.is_file():
                files.append(str(p.relative_to(job_dir)))
    return {"id": job_id, "artifact_root": str(job_dir), "files": files}
