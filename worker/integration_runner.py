from __future__ import annotations

import subprocess

ALLOWED_COMPOSE_FILE = "/srv/odyssey/openfactory/OpenFactory/docker-compose.pat.yml"
ALLOWED_ACTIONS = {"up", "down", "ps", "logs"}


def run_integration(action: str) -> subprocess.CompletedProcess[str]:
    if action not in ALLOWED_ACTIONS:
        raise RuntimeError(f"integration_action_not_allowed={action}")

    cmd = ["docker", "compose", "-f", ALLOWED_COMPOSE_FILE, action]
    if action == "up":
        cmd.append("-d")
    if action == "logs":
        cmd.extend(["--tail", "200"])
    return subprocess.run(cmd, check=False, text=True, capture_output=True)
