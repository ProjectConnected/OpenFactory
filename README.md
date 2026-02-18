# OpenFactory (Step 4 baseline)

This repo runs on the Factory VM.

## What it does
- API receives jobs from OpenClaw.
- Worker creates/uses repos, applies templates, runs tests, pushes a branch, opens a PR.
- "Done" is only declared after GitHub CI reports success for the PR head SHA.

## Host folders (Factory VM)
Create these on the Factory VM (owned by `botfactory`):
- `/srv/odyssey/secrets` (700)
  - `github_pat.txt` (600) : fine-grained PAT (or later: GitHub App token)
  - `openfactory_api_key.txt` (600) : random 32+ chars (OpenClaw must send it as header)
- `/srv/odyssey/workspaces` (for job sandboxes)
- `/srv/odyssey/data` (sqlite db)

## Run
```bash
cp .env.example .env
nano .env
docker compose -f docker-compose.pat.yml up -d --build
curl http://$OPENFACTORY_BIND_IP:8080/health
```

## OpenClaw integration
- `POST /v1/jobs` with header `X-OpenFactory-Key`
- poll `GET /v1/jobs/{id}` until `status=done` or `status=failed`
