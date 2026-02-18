import os, sqlite3, json, threading
from .utils import utc_now_iso

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL,
  request_json TEXT NOT NULL,
  result_json TEXT NOT NULL
);
"""

def _connect(db_path: str):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute(SCHEMA)
    return conn

def create_job(db_path: str, job_id: str, req: dict):
    with _lock:
        conn = _connect(db_path)
        now = utc_now_iso()
        conn.execute(
            "INSERT INTO jobs(id,created_at,updated_at,status,request_json,result_json) VALUES(?,?,?,?,?,?)",
            (job_id, now, now, "queued", json.dumps(req), json.dumps({})),
        )
        conn.close()

def update_job(db_path: str, job_id: str, status: str=None, result: dict=None):
    with _lock:
        conn = _connect(db_path)
        now = utc_now_iso()
        row = conn.execute("SELECT result_json,status FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            conn.close()
            raise KeyError(job_id)
        cur_result = json.loads(row[0] or "{}")
        if result:
            cur_result.update(result)
        new_status = status if status is not None else row[1]
        conn.execute(
            "UPDATE jobs SET updated_at=?, status=?, result_json=? WHERE id=?",
            (now, new_status, json.dumps(cur_result), job_id),
        )
        conn.close()

def get_job(db_path: str, job_id: str) -> dict:
    with _lock:
        conn = _connect(db_path)
        row = conn.execute(
            "SELECT id,created_at,updated_at,status,request_json,result_json FROM jobs WHERE id=?",
            (job_id,)
        ).fetchone()
        conn.close()
    if not row:
        raise KeyError(job_id)
    return {
        "id": row[0],
        "created_at": row[1],
        "updated_at": row[2],
        "status": row[3],
        "request": json.loads(row[4] or "{}"),
        "result": json.loads(row[5] or "{}"),
    }
