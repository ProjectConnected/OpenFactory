#!/usr/bin/env bash
set -euo pipefail

ROOT=${1:-/srv/odyssey/data/openfactory/jobs}
[[ -d "$ROOT" ]] || { echo "no artifact dir: $ROOT"; exit 0; }

find "$ROOT" -type f -name '*.log' | while read -r f; do
  perl -0777 -i -pe 's/gh[pousr]_[A-Za-z0-9_]+/[REDACTED_GITHUB_TOKEN]/g; s#x-access-token:[^@\s]+@#x-access-token:[REDACTED]@#g; s/(Authorization:\s*Bearer\s+)(\S+)/$1[REDACTED]/ig' "$f"
done

echo "artifact redaction complete"
