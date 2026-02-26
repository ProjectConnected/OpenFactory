from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class CoderRequest:
    repo_path: str
    ticket: str
    context: str


def _build_prompt(req: CoderRequest) -> str:
    return (
        "Generate ONLY a unified diff patch. No markdown. No prose.\n"
        "Do not run tools. Do not write files directly.\n"
        f"Repository path: {req.repo_path}\n"
        f"Ticket: {req.ticket}\n"
        f"Context: {req.context}\n"
    )


def _validate_patch(patch: str, err_code: str) -> str:
    patch = (patch or "").strip()
    if not patch.startswith("diff --git"):
        raise RuntimeError(err_code)
    return patch


class CliPatchProvider:
    def __init__(self, binary: str = "gemini", prompt_flag: str = "-p") -> None:
        self.binary = binary
        self.prompt_flag = prompt_flag

    def check_ready(self) -> None:
        try:
            v = subprocess.run([self.binary, "--version"], check=False, capture_output=True, text=True)
        except FileNotFoundError as e:
            raise RuntimeError(f"cli_missing install {self.binary} and authenticate") from e
        if v.returncode != 0:
            raise RuntimeError(f"cli_unavailable run '{self.binary} --version' and fix installation")

        probe_prompt = "Reply with exactly: READY"
        probe = subprocess.run(
            [self.binary, self.prompt_flag, probe_prompt],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "GEMINI_CLI_NONINTERACTIVE": "1"},
            timeout=45,
        )
        out = (probe.stdout or "") + (probe.stderr or "")
        if probe.returncode != 0 or "READY" not in out.upper():
            raise RuntimeError(f"cli_not_authenticated run '{self.binary} auth login' (or equivalent) on Factory VM")

    def generate_patch(self, req: CoderRequest) -> str:
        cp = subprocess.run(
            [self.binary, self.prompt_flag, _build_prompt(req)],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "GEMINI_CLI_NONINTERACTIVE": "1"},
            timeout=180,
        )
        if cp.returncode != 0:
            raise RuntimeError("cli_patch_generation_failed")
        return _validate_patch(cp.stdout or "", "cli_invalid_patch_output")


class GeminiApiProvider:
    def __init__(self, model: str = "gemini-2.5-pro") -> None:
        self.model = model

    def _api_key(self) -> str:
        key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if key:
            return key
        key_file = (os.getenv("GEMINI_API_KEY_FILE") or "/run/secrets/gemini_api_key.txt").strip()
        try:
            return open(key_file, "r", encoding="utf-8").read().strip()
        except FileNotFoundError as e:
            raise RuntimeError("gemini_api_key_missing") from e

    def check_ready(self) -> None:
        key = self._api_key()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={urllib.parse.quote(key)}"
        body = json.dumps({"contents": [{"parts": [{"text": "Reply with exactly: READY"}]}]}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                txt = resp.read().decode("utf-8", errors="ignore")
            if "READY" not in txt.upper():
                raise RuntimeError("gemini_api_probe_invalid")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"gemini_api_probe_http_{e.code}") from e
        except Exception as e:
            raise RuntimeError("gemini_api_probe_failed") from e

    def generate_patch(self, req: CoderRequest) -> str:
        key = self._api_key()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={urllib.parse.quote(key)}"
        prompt = _build_prompt(req)
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
        request = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=120) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"gemini_api_patch_http_{e.code}") from e
        except Exception as e:
            raise RuntimeError("gemini_api_patch_failed") from e

        parts = payload.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join((p.get("text") or "") for p in parts)
        return _validate_patch(text, "gemini_api_invalid_patch_output")
