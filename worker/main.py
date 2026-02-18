import json
import os
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

DB_PATH = os.getenv("OPENFACTORY_DB_PATH", "/data/openfactory.db")
WORKSPACES = Path(os.getenv("OPENFACTORY_WORKSPACES_DIR", "/workspaces"))
TOKEN_FILE = os.getenv("GITHUB_TOKEN_FILE", "/run/secrets/github_pat")
TEMPLATE_DIR = Path(os.getenv("TEMPLATE_DIR", "/app/templates/python-fastapi"))
BASE_BRANCH = os.getenv("BASE_BRANCH", "main")


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, check=False, text=True, capture_output=True)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or '').strip().replace('\n', ' | ')
        raise RuntimeError(f"cmd_failed rc={r.returncode} cmd={cmd} err={err[:1200]}")
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
    row = c.execute("SELECT id,payload_json FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
    if not row:
      c.close()
      return None
    c.execute("UPDATE jobs SET status='running', updated_at=? WHERE id=?", (now_iso(), row["id"]))
    c.commit()
    c.close()
    return row


def read_token():
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def apply_template(dst: Path):
    for p in TEMPLATE_DIR.rglob("*"):
        rel = p.relative_to(TEMPLATE_DIR)
        out = dst / rel
        if p.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out)


def create_pr_and_wait(owner, repo, branch, title, body):
    token = read_token()
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    r = s.post(f"https://api.github.com/repos/{owner}/{repo}/pulls", json={"title": title, "head": branch, "base": BASE_BRANCH, "body": body, "draft": True}, timeout=30)
    r.raise_for_status()
    pr = r.json()
    pr_url = pr["html_url"]
    pr_number = pr["number"]

    sha_r = s.get(f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}", timeout=30)
    sha_r.raise_for_status()
    head_sha = sha_r.json()["sha"]

    deadline = time.time() + 1800
    while time.time() < deadline:
        cr = s.get(f"https://api.github.com/repos/{owner}/{repo}/commits/{head_sha}/check-runs", timeout=30)
        cr.raise_for_status()
        checks = cr.json().get("check_runs", [])
        if checks:
            done = all(ch.get("status") == "completed" for ch in checks)
            green = all(ch.get("conclusion") == "success" for ch in checks if ch.get("status") == "completed")
            if done:
                return pr_url, ("green" if green else "red")
        time.sleep(15)
    return pr_url, "timeout"


def process(job_id, payload):
    owner = payload["owner"]
    repo = payload["repo"]
    task = payload["task"]
    branch = f"openfactory/{job_id[:8]}"

    ws = WORKSPACES / job_id
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True, exist_ok=True)

    token = read_token()
    repo_https = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
    run(["git", "clone", repo_https, str(ws)])
    run(["git", "checkout", "-b", branch], cwd=ws)

    apply_template(ws)

    readme = ws / "README.md"
    readme.write_text((readme.read_text(encoding="utf-8") if readme.exists() else "") + f"\n\nTask: {task}\n", encoding="utf-8")

    try:
        run(["python3", "-m", "compileall", "."], cwd=ws)
    except Exception:
        pass

    run(["git", "config", "user.name", "OpenFactory Bot"], cwd=ws)
    run(["git", "config", "user.email", "openfactory-bot@users.noreply.github.com"], cwd=ws)
    run(["git", "add", "-A"], cwd=ws)
    run(["git", "commit", "-m", "OpenFactory: apply template + task"], cwd=ws)
    run(["git", "remote", "set-url", "origin", repo_https], cwd=ws)
    run(["git", "push", "-u", "origin", branch], cwd=ws)

    pr_url, ci = create_pr_and_wait(owner, repo, branch, "OpenFactory: scaffold + task", task)
    if ci == "green":
        update_job(job_id, status="done", pr_url=pr_url, ci_status=ci)
    elif ci == "red":
        update_job(job_id, status="ci_failed", pr_url=pr_url, ci_status=ci)
    else:
        update_job(job_id, status="running", pr_url=pr_url, ci_status=ci)


def main():
    while True:
        job = claim_job()
        if not job:
            time.sleep(3)
            continue
        jid = job["id"]
        try:
            payload = json.loads(job["payload_json"])
            process(jid, payload)
        except Exception as e:
            update_job(jid, status="failed", error=str(e)[:2000])


if __name__ == "__main__":
    main()
