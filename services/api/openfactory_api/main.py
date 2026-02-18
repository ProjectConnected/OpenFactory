import os, uuid
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from redis import Redis
from rq import Queue

from openfactory_common.db import create_job, get_job
from openfactory_common.auth import load_api_key, api_key_ok

app = FastAPI(title="OpenFactory", version="0.1.0")

DB_PATH = os.environ.get("DB_PATH", "/data/openfactory.db")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
SECRETS_DIR = os.environ.get("SECRETS_DIR", "/secrets")
API_KEY_FILE = os.environ.get("OPENFACTORY_API_KEY_FILE", f"{SECRETS_DIR}/openfactory_api_key.txt")
GITHUB_OWNER_DEFAULT = os.environ.get("GITHUB_OWNER", "")

_expected_key = load_api_key(API_KEY_FILE)

redis = Redis.from_url(REDIS_URL)
q = Queue("openfactory", connection=redis, default_timeout=3600)

class JobRequest(BaseModel):
    repo_owner: str = Field(default="", description="GitHub org/user. Defaults to env GITHUB_OWNER.")
    repo_name: str = Field(..., description="Repository name to create/use.")
    create_repo: bool = Field(default=True, description="Create repo if missing (org repo).")
    private: bool = Field(default=True, description="Create repo private.")
    template: str = Field(default="python-fastapi", description="Template name under /templates.")
    task: str = Field(..., description="What to build/change.")
    coder_mode: str = Field(default="scaffold_only", description="scaffold_only | future: coder_loop")
    max_fix_loops: int = Field(default=0, ge=0, le=10, description="future: fix loop count")

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)
    got = request.headers.get("X-OpenFactory-Key", "")
    if not api_key_ok(got, _expected_key):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await call_next(request)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/v1/jobs")
def create(req: JobRequest):
    job_id = str(uuid.uuid4())
    payload = req.model_dump()
    if not payload["repo_owner"]:
        payload["repo_owner"] = GITHUB_OWNER_DEFAULT
    create_job(DB_PATH, job_id, payload)
    q.enqueue("openfactory_worker.jobs.run_job", job_id, payload)
    return {"id": job_id, "status": "queued"}

@app.get("/v1/jobs/{job_id}")
def status(job_id: str):
    return get_job(DB_PATH, job_id)
