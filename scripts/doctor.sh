#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="docker compose -f ${ROOT_DIR}/docker-compose.pat.yml"
FAILS=0

pass(){ echo "PASS: $*"; }
fail(){ echo "FAIL: $*"; FAILS=$((FAILS+1)); }

api_cid="$($COMPOSE ps -q api 2>/dev/null || true)"
worker_cid="$($COMPOSE ps -q worker 2>/dev/null || true)"
api_state=""; worker_state=""
[[ -n "$api_cid" ]] && api_state="$(docker inspect -f '{{.State.Status}}' "$api_cid" 2>/dev/null || true)"
[[ -n "$worker_cid" ]] && worker_state="$(docker inspect -f '{{.State.Status}}' "$worker_cid" 2>/dev/null || true)"
if [[ "$api_state" == "running" && "$worker_state" == "running" ]]; then
  pass "compose services running (api, worker)"
else
  fail "compose services not healthy api=${api_state:-missing} worker=${worker_state:-missing}"
fi

if $COMPOSE ps 2>/dev/null | grep -qi restarting; then
  fail "at least one service is restarting"
else
  pass "no service in restarting state"
fi

openapi="$(curl -fsS "http://127.0.0.1:8080/openapi.json" || true)"
if echo "$openapi" | grep -q '"/v1/jobs"'; then
  pass "openapi includes /v1/jobs"
else
  fail "openapi missing /v1/jobs"
fi
if echo "$openapi" | grep -q '"/v1/jobs/{job_id}/cancel"' && echo "$openapi" | grep -q '"/v1/jobs/{job_id}/artifacts"'; then
  pass "openapi includes cancel + artifacts endpoints"
else
  fail "openapi missing cancel/artifacts endpoints"
fi

if $COMPOSE exec -T worker test -s /run/secrets/github_pat; then
  pass "worker can read /run/secrets/github_pat"
else
  fail "worker cannot read /run/secrets/github_pat"
fi

if $COMPOSE exec -T worker sh -lc 'TOKEN=$(cat /run/secrets/github_pat); curl -fsS -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" https://api.github.com/user >/dev/null'; then
  pass "github auth succeeded"
else
  fail "github auth failed"
fi

if $COMPOSE exec -T worker sh -lc 'test -n "$OPENFACTORY_MODEL_PROVIDER_BASE_URL" && test -n "$OPENFACTORY_MODEL_NAME" && test -n "$OPENFACTORY_MODEL_TEMPERATURE" && test -n "$OPENFACTORY_MODEL_MAX_TOKENS"'; then
  pass "model config present for fail-fast"
else
  fail "model config env missing"
fi

ufw_out="$(sudo ufw status numbered || true)"
if echo "$ufw_out" | grep -q '22/tcp' && echo "$ufw_out" | grep -q '8080/tcp' && ! echo "$ufw_out" | grep -q '8080/tcp.*Anywhere'; then
  pass "ufw has scoped 22/tcp and 8080/tcp rules"
else
  fail "ufw rules are missing/overbroad for 22 or 8080"
fi

if [[ "$FAILS" -gt 0 ]]; then
  echo "doctor_result: FAIL ($FAILS checks failed)"
  exit 1
fi

echo "doctor_result: PASS"
