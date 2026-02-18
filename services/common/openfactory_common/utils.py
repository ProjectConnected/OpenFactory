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
