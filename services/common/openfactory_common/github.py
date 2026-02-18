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
