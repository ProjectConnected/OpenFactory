from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class CoderRequest:
    repo_path: str
    ticket: str
    context: str


class GeminiCliProvider:
    def __init__(self, binary: str = "gemini") -> None:
        self.binary = binary

    def check_ready(self) -> None:
        try:
            v = subprocess.run([self.binary, "--version"], check=False, capture_output=True, text=True)
        except FileNotFoundError as e:
            raise RuntimeError("gemini_cli_missing install gemini CLI and authenticate") from e
        if v.returncode != 0:
            raise RuntimeError("gemini_cli_unavailable run `gemini --version` and fix installation")

        probe_prompt = "Reply with exactly: READY"
        probe = subprocess.run(
            [self.binary, "-p", probe_prompt],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "GEMINI_CLI_NONINTERACTIVE": "1"},
            timeout=30,
        )
        out = (probe.stdout or "") + (probe.stderr or "")
        if probe.returncode != 0 or "READY" not in out.upper():
            raise RuntimeError("gemini_cli_not_authenticated run `gemini auth login` on Factory VM")

    def generate_patch(self, req: CoderRequest) -> str:
        prompt = (
            "Generate ONLY a unified diff patch. No markdown. No prose.\\n"
            "Do not run tools. Do not write files directly.\\n"
            f"Repository path: {req.repo_path}\\n"
            f"Ticket: {req.ticket}\\n"
            f"Context: {req.context}\\n"
        )
        cp = subprocess.run(
            [self.binary, "-p", prompt],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "GEMINI_CLI_NONINTERACTIVE": "1"},
            timeout=120,
        )
        if cp.returncode != 0:
            raise RuntimeError("gemini_cli_patch_generation_failed")
        patch = (cp.stdout or "").strip()
        if not patch.startswith("diff --git"):
            raise RuntimeError("gemini_cli_invalid_patch_output")
        return patch
