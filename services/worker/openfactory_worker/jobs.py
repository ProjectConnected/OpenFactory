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
