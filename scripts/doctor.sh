#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="docker compose -f ${ROOT_DIR}/docker-compose.pat.yml"
FAILS=0

pass(){ echo "PASS: $*"; }
warn(){ echo "WARN: $*"; }
fail(){ echo "FAIL: $*"; FAILS=$((FAILS+1)); }

api_cid="$($COMPOSE ps -q api 2>/dev/null || true)"
worker_cid="$($COMPOSE ps -q worker 2>/dev/null || true)"
api_state=""; worker_state=""
[[ -n "$api_cid" ]] && api_state="$(docker inspect -f '{{.State.Status}}' "$api_cid" 2>/dev/null || true)"
[[ -n "$worker_cid" ]] && worker_state="$(docker inspect -f '{{.State.Status}}' "$worker_cid" 2>/dev/null || true)"
if [[ "$api_state" == "running" && "$worker_state" == "running" ]]; then pass "compose services running (api, worker)"; else fail "compose services not healthy api=${api_state:-missing} worker=${worker_state:-missing}"; fi
if $COMPOSE ps 2>/dev/null | grep -qi restarting; then fail "at least one service is restarting"; else pass "no service in restarting state"; fi

openapi=""
for i in $(seq 1 20); do openapi="$(curl -fsS "http://127.0.0.1:8080/openapi.json" || true)"; [[ -n "$openapi" ]] && break; sleep 1; done
if echo "$openapi" | grep -q '"/v1/jobs"'; then pass "openapi includes /v1/jobs"; else fail "openapi missing /v1/jobs"; fi
if echo "$openapi" | grep -q '"/v1/jobs/{job_id}/cancel"' && echo "$openapi" | grep -q '"/v1/jobs/{job_id}/artifacts"'; then pass "openapi includes cancel + artifacts endpoints"; else fail "openapi missing cancel/artifacts endpoints"; fi

if $COMPOSE exec -T worker test -s /run/secrets/github_pat.txt; then pass "worker can read /run/secrets/github_pat.txt"; else fail "worker cannot read /run/secrets/github_pat.txt"; fi
if $COMPOSE exec -T worker sh -lc 'TOKEN=$(cat /run/secrets/github_pat.txt); curl -fsS -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" https://api.github.com/user >/dev/null'; then pass "github auth succeeded"; else fail "github auth failed"; fi

PRIMARY="$($COMPOSE exec -T worker sh -lc 'printf "%s" "${OPENFACTORY_CODER_PRIMARY:-}"' 2>/dev/null || true)"
FALLBACK="$($COMPOSE exec -T worker sh -lc 'printf "%s" "${OPENFACTORY_CODER_FALLBACK:-}"' 2>/dev/null || true)"
BIN="$($COMPOSE exec -T worker sh -lc 'printf "%s" "${OPENFACTORY_CODER_PROVIDER_BIN:-}"' 2>/dev/null || true)"
FLAG="$($COMPOSE exec -T worker sh -lc 'printf "%s" "${OPENFACTORY_CODER_PROMPT_FLAG:-}"' 2>/dev/null || true)"

if [[ -n "$PRIMARY" ]]; then pass "coder primary configured: $PRIMARY"; else fail "coder primary missing"; fi
if [[ "$PRIMARY" == *"cli"* || "$PRIMARY" == "cli" ]]; then
  if $COMPOSE exec -T worker sh -lc "command -v ${BIN:-qwen} >/dev/null 2>&1"; then pass "primary CLI binary available (${BIN:-qwen})"; else fail "primary CLI binary missing (${BIN:-qwen})"; fi
  if $COMPOSE exec -T worker sh -lc "${BIN:-qwen} ${FLAG:--p} 'Reply with exactly: READY' 2>/dev/null | grep -qi READY"; then
    pass "primary CLI non-interactive probe passed"
  else
    warn "primary CLI auth probe not ready yet (run ${BIN:-qwen} auth login)"
  fi
fi

if [[ "$FALLBACK" == "gemini_api" ]]; then
  if $COMPOSE exec -T worker sh -lc 'test -s "${GEMINI_API_KEY_FILE:-/run/secrets/gemini_api_key.txt}"'; then
    if $COMPOSE exec -T worker sh -lc 'KEY=$(cat "${GEMINI_API_KEY_FILE:-/run/secrets/gemini_api_key.txt}"); curl -fsS -X POST "https://generativelanguage.googleapis.com/v1beta/models/${OPENFACTORY_GEMINI_MODEL:-gemini-2.5-pro}:generateContent?key=${KEY}" -H "Content-Type: application/json" -d "{\"contents\":[{\"parts\":[{\"text\":\"Reply with READY\"}]}]}" >/dev/null'; then
      pass "gemini API fallback probe passed"
    else
      fail "gemini API fallback probe failed (invalid key/model/quota/network)"
    fi
  else
    fail "gemini API fallback configured but key file missing/empty"
  fi
else
  pass "gemini API fallback not enabled"
fi

if grep -RIlE 'gh[pousr]_[A-Za-z0-9_]+' /srv/odyssey/data/openfactory/jobs 2>/dev/null | head -n 1 | grep -q .; then fail "potential token leak found in artifacts (run scripts/redact_artifacts.sh)"; else pass "artifact logs pass token leak scan"; fi

if sudo -n true >/dev/null 2>&1; then
  ufw_out="$(sudo ufw status numbered || true)"
  if echo "$ufw_out" | grep -q '22/tcp' && echo "$ufw_out" | grep -q '8080/tcp' && ! echo "$ufw_out" | grep -q '8080/tcp.*Anywhere'; then pass "ufw has scoped 22/tcp and 8080/tcp rules"; else fail "ufw rules are missing/overbroad for 22 or 8080"; fi
else
  warn "skipping ufw check (sudo non-interactive not available)"
fi

if [[ "$FAILS" -gt 0 ]]; then echo "doctor_result: FAIL ($FAILS checks failed)"; exit 1; fi
echo "doctor_result: PASS"
