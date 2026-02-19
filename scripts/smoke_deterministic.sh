#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="docker compose -f ${ROOT_DIR}/docker-compose.pat.yml"
API_URL="${OPENFACTORY_API_URL:-http://127.0.0.1:8080}"
OWNER="${OPENFACTORY_SMOKE_OWNER:-ProjectConnected}"
REPO="${OPENFACTORY_SMOKE_REPO:-OpenFactorySmoke3}"
TIMEOUT_SEC="${OPENFACTORY_SMOKE_TIMEOUT_SEC:-1800}"

api_key="$($COMPOSE exec -T api sh -lc 'cat /run/secrets/openfactory_api_key' | tr -d '\r\n')"

submit_payload=$(cat <<JSON
{"owner":"${OWNER}","repo":"${REPO}","task":"Deterministic smoke: create hello-world FastAPI with /health and one test; keep changes minimal and CI-safe.","private":false,"template":"python-fastapi"}
JSON
)

submit_resp=$(curl -fsS -X POST "${API_URL}/v1/jobs" \
  -H "X-OpenFactory-Key: ${api_key}" \
  -H "Content-Type: application/json" \
  -d "${submit_payload}")

job_id=$(python3 - <<PY
import json
print(json.loads('''${submit_resp}''')['id'])
PY
)

echo "smoke_job_id=${job_id}"

start_ts=$(date +%s)
while true; do
  now_ts=$(date +%s)
  if (( now_ts - start_ts > TIMEOUT_SEC )); then
    echo "FAIL: timeout waiting for job terminal state"
    exit 2
  fi

  resp=$(curl -fsS "${API_URL}/v1/jobs/${job_id}" -H "X-OpenFactory-Key: ${api_key}")
  status=$(python3 - <<PY
import json
j=json.loads('''${resp}''')
print(j.get('status',''))
PY
)
  pr_url=$(python3 - <<PY
import json
j=json.loads('''${resp}''')
print(j.get('pr_url') or '')
PY
)
  ci=$(python3 - <<PY
import json
j=json.loads('''${resp}''')
print(j.get('ci_status') or '')
PY
)

  echo "status=${status} ci=${ci} pr=${pr_url}"

  case "$status" in
    done)
      if [[ -n "$pr_url" && "$ci" == "green" ]]; then
        echo "PASS: deterministic smoke complete"
        echo "PR_URL=${pr_url}"
        echo "CI_CONCLUSION=success"
        exit 0
      fi
      echo "FAIL: done but missing green ci/pr_url"
      exit 3
      ;;
    failed|ci_failed|cancelled)
      echo "FAIL: terminal failure status=${status}"
      exit 4
      ;;
  esac

  sleep 15
done
