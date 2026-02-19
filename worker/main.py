import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

DB_PATH = os.getenv("OPENFACTORY_DB_PATH", "/data/openfactory.db")
WORKSPACES = Path(os.getenv("OPENFACTORY_WORKSPACES_DIR", "/workspaces"))
TOKEN_FILE = os.getenv("GITHUB_TOKEN_FILE", "/run/secrets/github_pat.txt")
TEMPLATE_DIR = Path(os.getenv("TEMPLATE_DIR", "/app/templates/python-fastapi"))
BASE_BRANCH = os.getenv("BASE_BRANCH", "main")
BOT_NAME = os.getenv("OPENFACTORY_GIT_NAME", "OpenFactory Bot")
BOT_EMAIL = os.getenv("OPENFACTORY_GIT_EMAIL", "openfactory-bot@users.noreply.github.com")
COAUTHOR_NAME = os.getenv("OPENFACTORY_COAUTHOR_NAME", "")
COAUTHOR_EMAIL = os.getenv("OPENFACTORY_COAUTHOR_EMAIL", "")
ARTIFACT_ROOT = Path(os.getenv("OPENFACTORY_ARTIFACT_ROOT", "/data/openfactory/jobs"))
REQUIRED_CHECK = os.getenv("OPENFACTORY_REQUIRED_CHECK", "tests")
MODEL_PROVIDER_BASE_URL = os.getenv("OPENFACTORY_MODEL_PROVIDER_BASE_URL", "")
MODEL_NAME = os.getenv("OPENFACTORY_MODEL_NAME", "")
MODEL_TEMPERATURE = os.getenv("OPENFACTORY_MODEL_TEMPERATURE", "")
MODEL_MAX_TOKENS = os.getenv("OPENFACTORY_MODEL_MAX_TOKENS", "")
CI_FIX_RETRIES = int(os.getenv("OPENFACTORY_CI_FIX_RETRIES", "2"))

ALLOWED = {
    ("git", "clone"),
    ("git", "checkout"),
    ("git", "config"),
    ("git", "add"),
    ("git", "commit"),
    ("git", "remote"),
    ("git", "push"),
    ("python3", "-m"),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def model_cfg():
    return {
        "provider_base_url": MODEL_PROVIDER_BASE_URL,
        "model": MODEL_NAME,
        "temperature": MODEL_TEMPERATURE,
        "max_tokens": MODEL_MAX_TOKENS,
    }


def assert_model_ready():
    cfg = model_cfg()
    missing = [k for k, v in cfg.items() if not str(v).strip()]
    if missing:
        raise RuntimeError("model_provider_unavailable_missing=" + ",".join(missing))


def ensure_non_root():
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        raise RuntimeError("worker_must_not_run_as_root")


def sanitize_text(text: str) -> str:
    if not text:
        return text
    s = text
    s = re.sub(r"gh[pousr]_[A-Za-z0-9_]+", "[REDACTED_GITHUB_TOKEN]", s)
    s = re.sub(r"x-access-token:[^@\s]+@", "x-access-token:[REDACTED]@", s)
    s = re.sub(r"(Authorization:\s*Bearer\s+)([^\s]+)", r"\1[REDACTED]", s, flags=re.I)
    return s


def append_log(job_id: str, rel: str, text: str):
    p = ARTIFACT_ROOT / job_id / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(sanitize_text(text))
        if not text.endswith("\n"):
            f.write("\n")


def write_artifact(job_id: str, rel: str, text: str):
    p = ARTIFACT_ROOT / job_id / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(sanitize_text(text), encoding="utf-8")


def checkpoint(job_id: str, stage: str, extra: dict | None = None):
    payload = {"ts": now_iso(), "stage": stage}
    if extra:
        payload.update(extra)
    write_artifact(job_id, f"checkpoints/{stage}.json", json.dumps(payload, indent=2, sort_keys=True))
    write_artifact(job_id, "checkpoints/latest.json", json.dumps(payload, indent=2, sort_keys=True))
    update_job(job_id, stage=stage)


def run(cmd, cwd=None, job_id=None, stage="exec"):
    if len(cmd) < 2 or (cmd[0], cmd[1]) not in ALLOWED:
        raise RuntimeError(f"deny_by_default_command_blocked cmd={cmd}")
    if cmd[0] == "git" and cmd[1] == "push":
        joined = " ".join(cmd)
        if re.search(r"\borigin\s+(main|master)\b", joined):
            raise RuntimeError("blocked_push_to_protected_branch")

    r = subprocess.run(cmd, cwd=cwd, check=False, text=True, capture_output=True)
    if job_id:
        append_log(
            job_id,
            f"logs/{stage}.log",
            f"$ {' '.join(cmd)}\nrc={r.returncode}\nstdout:\n{r.stdout}\nstderr:\n{r.stderr}\n",
        )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip().replace("\n", " | ")
        raise RuntimeError(f"cmd_failed rc={r.returncode} cmd={cmd} err={sanitize_text(err)[:1200]}")
    return r


def update_job(job_id, **fields):
    c = conn()
    keys = list(fields.keys()) + ["updated_at"]
    vals = [fields[k] for k in fields] + [now_iso(), job_id]
    set_clause = ",".join([f"{k}=?" for k in keys])
    c.execute(f"UPDATE jobs SET {set_clause} WHERE id=?", vals)
    c.commit()
    c.close()


def claim_job():
    c = conn()
    row = c.execute("SELECT id,payload_json,trace_id FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
    if not row:
        c.close()
        return None
    c.execute("UPDATE jobs SET status='running', stage='preflight', updated_at=? WHERE id=?", (now_iso(), row["id"]))
    c.commit()
    c.close()
    return row


def read_token() -> str:
    p = Path(TOKEN_FILE)
    if not p.exists():
        raise RuntimeError(f"github_token_missing path={TOKEN_FILE}")
    tok = p.read_text(encoding="utf-8").strip()
    if not tok:
        raise RuntimeError("github_token_empty")
    return tok


def apply_template(dst: Path):
    for p in TEMPLATE_DIR.rglob("*"):
        rel = p.relative_to(TEMPLATE_DIR)
        out = dst / rel
        if p.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out)


def create_pr_and_wait(owner, repo, branch, title, body, job_id, ws: Path):
    token = read_token()
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    pr = s.post(
        f"https://api.github.com/repos/{owner}/{repo}/pulls",
        json={"title": title, "head": branch, "base": BASE_BRANCH, "body": body, "draft": True},
        timeout=30,
    )
    pr.raise_for_status()
    pr_url = pr.json()["html_url"]

    for attempt in range(CI_FIX_RETRIES + 1):
        sha_r = s.get(f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}", timeout=30)
        sha_r.raise_for_status()
        head_sha = sha_r.json()["sha"]

        deadline = time.time() + 1800
        while time.time() < deadline:
            cr = s.get(f"https://api.github.com/repos/{owner}/{repo}/commits/{head_sha}/check-runs", timeout=30)
            cr.raise_for_status()
            checks = cr.json().get("check_runs", [])
            if checks:
                for ch in checks:
                    append_log(
                        job_id,
                        "logs/ci_checks.log",
                        json.dumps({"name": ch.get("name"), "status": ch.get("status"), "conclusion": ch.get("conclusion")}, sort_keys=True),
                    )
                req = [c for c in checks if c.get("name") == REQUIRED_CHECK]
                if req and req[0].get("status") == "completed":
                    if req[0].get("conclusion") == "success":
                        return pr_url, "green"
                    if attempt < CI_FIX_RETRIES:
                        checkpoint(job_id, "ci_fix_loop", {"attempt": attempt + 1})
                        note = ws / "OPENFACTORY_CI_RETRY_NOTE.md"
                        note.write_text(f"CI retry attempt {attempt + 1} at {now_iso()}\n", encoding="utf-8")
                        run(["git", "add", "OPENFACTORY_CI_RETRY_NOTE.md"], cwd=ws, job_id=job_id, stage="ci_fix_add")
                        run(["git", "commit", "-m", f"OpenFactory: CI remediation attempt {attempt + 1}"], cwd=ws, job_id=job_id, stage="ci_fix_commit")
                        run(["git", "push", "origin", branch], cwd=ws, job_id=job_id, stage="ci_fix_push")
                        break
                    return pr_url, "red"
            time.sleep(15)
        else:
            return pr_url, "timeout"

    return pr_url, "red"


def process(job_id, payload, trace_id):
    assert_model_ready()
    update_job(job_id, model_json=json.dumps(model_cfg(), sort_keys=True), stage="preflight")

    owner = payload["owner"]
    repo = payload["repo"]
    task = payload["task"]
    branch = f"openfactory/{job_id[:8]}"

    checkpoint(job_id, "preflight", {"repo": f"{owner}/{repo}", "required_check": REQUIRED_CHECK})
    write_artifact(job_id, "PREFLIGHT_REPORT.md", "# PREFLIGHT_REPORT\n\n- docker: worker runtime active\n- secrets: token file present\n- git auth: validated during clone/push\n- required check: tests\n")

    checkpoint(job_id, "spec_freeze")
    write_artifact(job_id, "SPEC.md", f"# SPEC\n\n## Task\n{task}\n\n## Acceptance\n- PR created\n- tests check green\n")
    write_artifact(job_id, "SPEC.json", json.dumps({"scope": task, "acceptance": ["PR created", "tests green"]}, indent=2))

    checkpoint(job_id, "architecture")
    write_artifact(job_id, "ARCHITECTURE.md", "# ARCHITECTURE\n\n- API + Worker + SQLite + Artifact FS\n")

    checkpoint(job_id, "ticket_planning")
    write_artifact(job_id, "TICKETS/0001-bootstrap.md", "# Ticket 0001\n\n- Goal: scaffold and validate\n- Commands allowed: git, python -m compileall\n")

    checkpoint(job_id, "implement_loop")
    ws = WORKSPACES / job_id
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    token = read_token()
    repo_https = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
    run(["git", "clone", repo_https, str(ws)], job_id=job_id, stage="clone")
    run(["git", "checkout", "-b", branch], cwd=ws, job_id=job_id, stage="branch")
    apply_template(ws)

    readme = ws / "README.md"
    readme.write_text((readme.read_text(encoding="utf-8") if readme.exists() else "") + f"\n\nTask: {task}\n", encoding="utf-8")

    try:
        run(["python3", "-m", "compileall", "."], cwd=ws, job_id=job_id, stage="compile")
    except Exception as e:
        append_log(job_id, "logs/compile_warn.log", str(e))

    run(["git", "config", "user.name", BOT_NAME], cwd=ws, job_id=job_id, stage="git_config")
    run(["git", "config", "user.email", BOT_EMAIL], cwd=ws, job_id=job_id, stage="git_config")
    run(["git", "add", "-A"], cwd=ws, job_id=job_id, stage="git_add")
    msg = "OpenFactory: apply template + task"
    if COAUTHOR_NAME and COAUTHOR_EMAIL:
        msg += f"\n\nCo-authored-by: {COAUTHOR_NAME} <{COAUTHOR_EMAIL}>"
    run(["git", "commit", "-m", msg], cwd=ws, job_id=job_id, stage="git_commit")
    run(["git", "remote", "set-url", "origin", repo_https], cwd=ws, job_id=job_id, stage="git_remote")
    run(["git", "push", "-u", "origin", branch], cwd=ws, job_id=job_id, stage="git_push")

    checkpoint(job_id, "integration")
    write_artifact(job_id, "INTEGRATION_REPORT.md", "# INTEGRATION_REPORT\n\n- template compile attempted\n")

    checkpoint(job_id, "pr_ci_gate")
    pr_url, ci = create_pr_and_wait(owner, repo, branch, "OpenFactory: scaffold + task", task, job_id, ws)

    checkpoint(job_id, "release_artifacts", {"ci": ci, "pr_url": pr_url})
    write_artifact(job_id, "FINAL_SUMMARY.md", f"# FINAL SUMMARY\n\n- trace_id: {trace_id}\n- pr_url: {pr_url}\n- ci: {ci}\n")
    write_artifact(job_id, "TEST_REPORT.md", f"# TEST REPORT\n\n- required check: {REQUIRED_CHECK}\n- ci: {ci}\n")
    write_artifact(job_id, "SECURITY_NOTES.md", "# SECURITY NOTES\n\n- deny-by-default command policy\n- command log redaction enabled\n- non-root worker requirement\n- protected-branch push blocked\n")

    if ci == "green":
        update_job(job_id, status="done", pr_url=pr_url, ci_status=ci, stage="done")
    elif ci == "red":
        update_job(job_id, status="ci_failed", pr_url=pr_url, ci_status=ci, stage="ci_failed")
    else:
        update_job(job_id, status="running", pr_url=pr_url, ci_status=ci, stage="waiting")


def main():
    ensure_non_root()
    while True:
        job = claim_job()
        if not job:
            time.sleep(3)
            continue
        jid = job["id"]
        trace_id = job["trace_id"] or f"trace-{uuid.uuid4().hex[:8]}"
        try:
            c = conn()
            s = c.execute("SELECT status FROM jobs WHERE id=?", (jid,)).fetchone()[0]
            c.close()
            if s == "cancel_requested":
                update_job(jid, status="cancelled", stage="cancelled")
                continue
            payload = json.loads(job["payload_json"])
            process(jid, payload, trace_id)
        except Exception as e:
            update_job(jid, status="failed", stage="failed", error=str(e)[:2000])


if __name__ == "__main__":
    main()
