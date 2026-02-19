#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/srv/odyssey/openfactory/OpenFactory"
SERVICE="openfactory.service"

if ! curl -fsS http://127.0.0.1:8080/openapi.json | grep -q '"/v1/jobs"'; then
  sudo systemctl restart "$SERVICE"
fi
