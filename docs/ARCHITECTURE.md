# OpenFactory Architecture (v1)

## Components
- `api`: FastAPI service on host port `8080`, backed by sqlite at `/srv/odyssey/data/openfactory.db`
- `worker`: polls queued jobs, clones target repos, applies template, opens PR, waits on CI

## Runtime model
- Single canonical deployment path: `/srv/odyssey/openfactory/OpenFactory`
- Managed by `openfactory.service` (systemd), with `openfactory-watchdog.timer` checking API health every 60s
- API externally reachable at `http://100.102.56.104:8080`

## Secrets
- Canonical host secret directory: `/srv/odyssey/secrets`
- `docker-compose.pat.yml` mounts secrets via Compose secrets:
  - `/run/secrets/openfactory_api_key`
  - `/run/secrets/github_pat`
- Worker reads token from `/run/secrets/github_pat` (or env override)

## Recovery behavior
- First response: `make doctor`
- Automatic response: watchdog restarts service when `/openapi.json` missing `/v1/jobs` or API not reachable
- Manual fallback: restart service and inspect journald + container logs
