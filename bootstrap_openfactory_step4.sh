#!/usr/bin/env bash
set -euo pipefail

# OpenFactory Step 4 baseline generator
# Run from repo root. It will CREATE/OVERWRITE files under services/ and templates/.

mkdir -p services/common/openfactory_common
mkdir -p services/api/openfactory_api
mkdir -p services/worker/openfactory_worker
mkdir -p templates/python-fastapi/app
mkdir -p templates/python-fastapi/tests
mkdir -p templates/python-fastapi/.github/workflows

cat > .gitignore <<'GIT'
.env
data/
workspaces/
secrets/
__pycache__/
*.pyc
*.pyo
*.pyd
*.db
*.log
*.sqlite*
.venv/
.DS_Store
GIT

cat > .env.example <<'ENV'
# Bind API to your Tailscale IP (recommended) so it's not exposed on LAN
# Example: OPENFACTORY_BIND_IP=100.102.56.104
OPENFACTORY_BIND_IP=100.x.y.z

# GitHub org/user that will own created repos
GITHUB_OWNER=ProjectConnected

# Author attribution for commits OpenFactory makes (optional)
GIT_AUTHOR_NAME=openfactory-bot
GIT_AUTHOR_EMAIL=YOUR_VERIFIED_NO_REPLY@users.noreply.github.com

# Host UID/GID so container writes as your botfactory user
HOST_UID=1000
HOST_GID=1000

# Internal paths inside containers
SECRETS_DIR=/secrets
WORKSPACES_ROOT=/workspaces
DB_PATH=/data/openfactory.db
REDIS_URL=redis://redis:6379/0
ENV

cat > README.md <<'MD'
# OpenFactory (Step 4 baseline)

This repo runs on the Factory VM.

## What it does
- API receives jobs from OpenClaw.
- Worker creates/uses repos, applies templates, runs tests, pushes a branch, opens a PR.
- "Done" is only declared after GitHub CI reports success for the PR head SHA.

## Host folders (Factory VM)
Create these on the Factory VM (owned by `botfactory`):
- `/srv/odyssey/secrets` (700)
  - `github_pat.txt` (600) : fine-grained PAT (or later: GitHub App token)
  - `openfactory_api_key.txt` (600) : random 32+ chars (OpenClaw must send it as header)
- `/srv/odyssey/workspaces` (for job sandboxes)
- `/srv/odyssey/data` (sqlite db)

## Run
```bash
cp .env.example .env
nano .env
docker compose -f docker-compose.pat.yml up -d --build
curl http://$OPENFACTORY_BIND_IP:8080/health
```

## OpenClaw integration
- `POST /v1/jobs` with header `X-OpenFactory-Key`
- poll `GET /v1/jobs/{id}` until `status=done` or `status=failed`
MD

cat > docker-compose.pat.yml <<'YML'
services:
  redis:
    image: redis:7-alpine
    command: ["redis-server","--save","","--appendonly","no"]
    networks: [openfactory]
    read_only: true
    tmpfs:
      - /tmp
      - /data
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    pids_limit: 200
    healthcheck:
      test: ["CMD","redis-cli","ping"]
      interval: 5s
      timeout: 3s
      retries: 20
    restart: unless-stopped

  api:
    build:
      context: .
      dockerfile: services/api/Dockerfile
    init: true
    user: "${HOST_UID}:${HOST_GID}"
    environment:
      - REDIS_URL=${REDIS_URL}
      - DB_PATH=${DB_PATH}
      - SECRETS_DIR=${SECRETS_DIR}
      - OPENFACTORY_API_KEY_FILE=${SECRETS_DIR}/openfactory_api_key.txt
      - GITHUB_OWNER=${GITHUB_OWNER}
      - PYTHONDONTWRITEBYTECODE=1
      - PYTHONUNBUFFERED=1
    volumes:
      - /srv/odyssey/data:/data
      - /srv/odyssey/secrets:/secrets:ro
    ports:
      - "${OPENFACTORY_BIND_IP:-0.0.0.0}:8080:8080"
    depends_on:
      redis:
        condition: service_healthy
    networks: [openfactory]
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    pids_limit: 300
    healthcheck:
      test: ["CMD","python","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health').read()"]
      interval: 10s
      timeout: 3s
      retries: 20
    restart: unless-stopped

  worker:
    build:
      context: .
      dockerfile: services/worker/Dockerfile
    init: true
    user: "${HOST_UID}:${HOST_GID}"
    environment:
      - REDIS_URL=${REDIS_URL}
      - DB_PATH=${DB_PATH}
      - WORKSPACES_ROOT=${WORKSPACES_ROOT}
      - SECRETS_DIR=${SECRETS_DIR}
      - OPENFACTORY_API_KEY_FILE=${SECRETS_DIR}/openfactory_api_key.txt
      - GITHUB_TOKEN_FILE=${SECRETS_DIR}/github_pat.txt
      - GITHUB_OWNER=${GITHUB_OWNER}
      - GIT_AUTHOR_NAME=${GIT_AUTHOR_NAME}
      - GIT_AUTHOR_EMAIL=${GIT_AUTHOR_EMAIL}
      - CODER_MODE=scaffold_only
      - MAX_FIX_LOOPS=0
      - PYTHONDONTWRITEBYTECODE=1
      - PYTHONUNBUFFERED=1
    volumes:
      - /srv/odyssey/data:/data
      - /srv/odyssey/workspaces:/workspaces
      - /srv/odyssey/secrets:/secrets:ro
    depends_on:
      redis:
        condition: service_healthy
      api:
        condition: service_healthy
    networks: [openfactory]
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    pids_limit: 800
    restart: unless-stopped

networks:
  openfactory:
    driver: bridge
YML

# ---------------- common python (no FastAPI deps) ----------------
cat > services/common/openfactory_common/__init__.py <<'PY'
PY

cat > services/common/openfactory_common/utils.py <<'PY'
import os, subprocess, json, time
from datetime import datetime, timezone

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def read_secret(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

def run_cmd(args, cwd=None, env=None, timeout=900, redact=None) -> str:
    """
    Run command safely (no shell), capture output.
    redact: list[str] to redact from output.
    """
    env2 = os.environ.copy()
    if env:
        env2.update(env)
    env2["GIT_TERMINAL_PROMPT"] = "0"
    p = subprocess.run(
        args,
        cwd=cwd,
        env=env2,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        text=True,
        check=False,
    )
    out = p.stdout or ""
    if redact:
        for r in redact:
            if r:
                out = out.replace(r, "***REDACTED***")
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {args}\n{out}")
    return out

def sleep_s(seconds: float):
    time.sleep(seconds)

def jdump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)
PY

cat > services/common/openfactory_common/auth.py <<'PY'
import hmac
from .utils import read_secret

def load_api_key(api_key_file: str) -> str:
    k = read_secret(api_key_file)
    if len(k) < 16:
        raise RuntimeError("openfactory_api_key.txt too short; use 32+ chars")
    return k

def api_key_ok(got: str, expected: str) -> bool:
    # constant-time compare
    return hmac.compare_digest(got or "", expected or "")
PY

cat > services/common/openfactory_common/db.py <<'PY'
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
PY

cat > services/common/openfactory_common/github.py <<'PY'
import requests
from .utils import run_cmd, read_secret, sleep_s

API = "https://api.github.com"

def gh_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

def gh_get(token: str, url: str):
    r = requests.get(url, headers=gh_headers(token), timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"GitHub GET {url} -> {r.status_code} {r.text}")
    return r.json()

def gh_post(token: str, url: str, payload: dict):
    r = requests.post(url, headers=gh_headers(token), json=payload, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"GitHub POST {url} -> {r.status_code} {r.text}")
    return r.json()

def get_repo(token: str, owner: str, repo: str) -> dict:
    return gh_get(token, f"{API}/repos/{owner}/{repo}")

def ensure_repo_exists(token: str, owner: str, repo: str, private: bool=True):
    url = f"{API}/repos/{owner}/{repo}"
    r = requests.get(url, headers=gh_headers(token), timeout=30)
    if r.status_code == 200:
        return r.json()
    if r.status_code != 404:
        raise RuntimeError(f"GitHub GET {url} -> {r.status_code} {r.text}")
    # Create as ORG repo
    create_url = f"{API}/orgs/{owner}/repos"
    payload = {"name": repo, "private": private, "auto_init": True}
    return gh_post(token, create_url, payload)

def _askpass_script(repo_dir: str, token_file: str) -> str:
    # Git calls askpass with prompt text in $1.
    # We return username for Username prompts, token for Password prompts.
    path = f"{repo_dir}/.openfactory_askpass.sh"
    token = read_secret(token_file)
    with open(path, "w", encoding="utf-8") as f:
        f.write("#!/bin/sh\n")
        f.write("case \"$1\" in\n")
        f.write("  *Username*) echo \"x-access-token\" ;;\n")
        f.write(f"  *) cat \"{token_file}\" ;;\n")
        f.write("esac\n")
    run_cmd(["chmod","700",path])
    return path

def clone_repo(owner: str, repo: str, token_file: str, dst: str):
    # No token in remote URL, avoids leaking token into git config.
    # We rely on GIT_ASKPASS to supply credentials.
    env = {}
    askpass_dir = dst + "_tmp"
    run_cmd(["mkdir","-p",askpass_dir])
    askpass = _askpass_script(askpass_dir, token_file)
    env["GIT_ASKPASS"] = askpass
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        run_cmd(["git","clone",f"https://github.com/{owner}/{repo}.git",dst], env=env, redact=[read_secret(token_file)])
    finally:
        run_cmd(["rm","-rf",askpass_dir], timeout=30)

def create_branch(repo_dir: str, branch: str):
    run_cmd(["git","checkout","-b",branch], cwd=repo_dir)

def commit_all(repo_dir: str, message: str, author_name: str, author_email: str):
    run_cmd(["git","config","user.name",author_name], cwd=repo_dir)
    run_cmd(["git","config","user.email",author_email], cwd=repo_dir)
    run_cmd(["git","add","-A"], cwd=repo_dir)
    st = run_cmd(["git","status","--porcelain"], cwd=repo_dir)
    if not st.strip():
        return False
    run_cmd(["git","commit","-m",message], cwd=repo_dir)
    return True

def push_branch(repo_dir: str, token_file: str, branch: str):
    env = {
        "GIT_ASKPASS": _askpass_script(repo_dir, token_file),
        "GIT_TERMINAL_PROMPT": "0",
    }
    try:
        run_cmd(["git","push","-u","origin",branch], cwd=repo_dir, env=env, redact=[read_secret(token_file)])
    finally:
        # best-effort cleanup
        try:
            run_cmd(["rm","-f",f"{repo_dir}/.openfactory_askpass.sh"], timeout=30)
        except Exception:
            pass

def open_pr(token: str, owner: str, repo: str, head: str, base: str, title: str, body: str, draft: bool=True):
    url = f"{API}/repos/{owner}/{repo}/pulls"
    return gh_post(token, url, {
        "title": title,
        "body": body,
        "head": head,
        "base": base,
        "draft": draft
    })

def wait_for_combined_status_green(token: str, owner: str, repo: str, sha: str, timeout_s: int=1800):
    """
    Poll combined status endpoint.
    Returns ok=True only if state == success.
    """
    url = f"{API}/repos/{owner}/{repo}/commits/{sha}/status"
    remaining = timeout_s
    while remaining > 0:
        data = gh_get(token, url)
        state = (data.get("state") or "").lower()
        if state == "success":
            return {"ok": True, "state": state}
        if state in ("failure", "error"):
            return {"ok": False, "state": state}
        sleep_s(10)
        remaining -= 10
    return {"ok": False, "timeout": True}
PY

# ---------------- API service ----------------
cat > services/api/Dockerfile <<'DOCKER'
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY services/api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/common/openfactory_common /app/openfactory_common
COPY services/api/openfactory_api /app/openfactory_api

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8080
CMD ["python","-m","uvicorn","openfactory_api.main:app","--host","0.0.0.0","--port","8080"]
DOCKER

cat > services/api/requirements.txt <<'REQ'
fastapi==0.115.8
uvicorn[standard]==0.30.6
redis==5.0.8
rq==1.16.2
REQ

cat > services/api/openfactory_api/__init__.py <<'PY'
PY

cat > services/api/openfactory_api/main.py <<'PY'
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
PY

# ---------------- Worker service ----------------
cat > services/worker/Dockerfile <<'DOCKER'
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends     git make     && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY services/worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/common/openfactory_common /app/openfactory_common
COPY services/worker/openfactory_worker /app/openfactory_worker
COPY templates /templates

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["python","-m","openfactory_worker.worker"]
DOCKER

cat > services/worker/requirements.txt <<'REQ'
redis==5.0.8
rq==1.16.2
requests==2.32.3
REQ

cat > services/worker/openfactory_worker/__init__.py <<'PY'
PY

cat > services/worker/openfactory_worker/worker.py <<'PY'
import os
from redis import Redis
from rq import Worker, Queue, Connection

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

def main():
    r = Redis.from_url(REDIS_URL)
    with Connection(r):
        w = Worker([Queue("openfactory")])
        w.work(with_scheduler=False)

if __name__ == "__main__":
    main()
PY

cat > services/worker/openfactory_worker/jobs.py <<'PY'
import os, shutil
from pathlib import Path

from openfactory_common.db import update_job
from openfactory_common.utils import read_secret, run_cmd
from openfactory_common.github import (
    ensure_repo_exists, get_repo, clone_repo, create_branch, commit_all, push_branch, open_pr,
    wait_for_combined_status_green
)

DB_PATH = os.environ.get("DB_PATH", "/data/openfactory.db")
WORKSPACES_ROOT = os.environ.get("WORKSPACES_ROOT", "/workspaces")
SECRETS_DIR = os.environ.get("SECRETS_DIR", "/secrets")
TOKEN_FILE = os.environ.get("GITHUB_TOKEN_FILE", f"{SECRETS_DIR}/github_pat.txt")

GIT_AUTHOR_NAME = os.environ.get("GIT_AUTHOR_NAME", "openfactory-bot")
GIT_AUTHOR_EMAIL = os.environ.get("GIT_AUTHOR_EMAIL", "bot@localhost")

def copy_template(template_name: str, dst: Path):
    src = Path("/templates") / template_name
    if not src.exists():
        raise RuntimeError(f"Template not found: {template_name}")
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)

def run_template_tests(repo_dir: Path):
    run_cmd(["python","-m","venv",".venv"], cwd=str(repo_dir), timeout=300)
    run_cmd([".venv/bin/pip","install","-r","requirements.txt"], cwd=str(repo_dir), timeout=900)
    run_cmd([".venv/bin/pytest","-q"], cwd=str(repo_dir), timeout=900)

def run_job(job_id: str, req: dict):
    token = read_secret(TOKEN_FILE)
    owner = req["repo_owner"]
    repo = req["repo_name"]
    template = req.get("template", "python-fastapi")
    task = req.get("task", "")
    create_repo_flag = bool(req.get("create_repo", True))
    private = bool(req.get("private", True))

    ws = Path(WORKSPACES_ROOT) / f"{repo}-{job_id}"
    repo_dir = ws / repo
    branch = f"openfactory/{job_id[:8]}"

    update_job(DB_PATH, job_id, status="starting", result={"workspace": str(ws)})

    try:
        if create_repo_flag:
            update_job(DB_PATH, job_id, status="ensure_repo")
            ensure_repo_exists(token, owner, repo, private=private)

        update_job(DB_PATH, job_id, status="repo_info")
        info = get_repo(token, owner, repo)
        base_branch = info.get("default_branch", "main")

        update_job(DB_PATH, job_id, status="clone")
        ws.mkdir(parents=True, exist_ok=True)
        clone_repo(owner, repo, TOKEN_FILE, str(repo_dir))

        update_job(DB_PATH, job_id, status="branch")
        create_branch(str(repo_dir), branch)

        update_job(DB_PATH, job_id, status="apply_template")
        copy_template(template, repo_dir)

        (repo_dir / "OPENFACTORY_TASK.md").write_text(f"# Task\n\n{task}\n", encoding="utf-8")

        update_job(DB_PATH, job_id, status="test_local")
        run_template_tests(repo_dir)

        update_job(DB_PATH, job_id, status="commit")
        committed = commit_all(str(repo_dir), f"OpenFactory: scaffold {template}", GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL)
        if not committed:
            update_job(DB_PATH, job_id, status="no_changes", result={"note": "No changes to commit"})
            return

        update_job(DB_PATH, job_id, status="push")
        push_branch(str(repo_dir), TOKEN_FILE, branch)

        update_job(DB_PATH, job_id, status="open_pr")
        pr = open_pr(
            token, owner, repo,
            head=branch,
            base=base_branch,
            title=f"OpenFactory scaffold: {template}",
            body=f"Job: {job_id}\n\nTask:\n{task}\n",
            draft=True
        )

        pr_url = pr.get("html_url", "")
        sha = (pr.get("head") or {}).get("sha", "")
        if not sha:
            sha = run_cmd(["git","rev-parse","HEAD"], cwd=str(repo_dir)).strip()

        update_job(DB_PATH, job_id, status="pr_opened", result={"pr_url": pr_url, "head_sha": sha, "base": base_branch})

        update_job(DB_PATH, job_id, status="ci_wait")
        ci = wait_for_combined_status_green(token, owner, repo, sha, timeout_s=1800)

        update_job(DB_PATH, job_id, status=("done" if ci.get("ok") else "failed"), result={"ci": ci})

    except Exception as e:
        update_job(DB_PATH, job_id, status="failed", result={"error": str(e)})
        raise
PY

# ---------------- Template: python-fastapi ----------------
cat > templates/python-fastapi/README.md <<'MD'
# python-fastapi template

Includes:
- FastAPI app with /health
- pytest
- GitHub Actions CI workflow (runs on PRs)
MD

cat > templates/python-fastapi/requirements.txt <<'REQ'
fastapi==0.115.8
uvicorn[standard]==0.30.6
pytest==8.3.4
httpx==0.27.2
REQ

cat > templates/python-fastapi/app/main.py <<'PY'
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}
PY

cat > templates/python-fastapi/tests/test_health.py <<'PY'
from app.main import app
from fastapi.testclient import TestClient

def test_health():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json().get("ok") is True
PY

cat > templates/python-fastapi/.github/workflows/ci.yml <<'YML'
name: tests
on:
  pull_request:
  push:
    branches: [ "main" ]

jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install -r requirements.txt
      - run: pytest -q
YML

echo "Step 4 files generated."
echo "Next:"
echo "  1) cp .env.example .env && nano .env"
echo "  2) Create /srv/odyssey/{secrets,workspaces,data} and secrets files"
echo "  3) docker compose -f docker-compose.pat.yml up -d --build"

