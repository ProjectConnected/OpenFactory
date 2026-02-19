# Storage Migration: SQLite -> Postgres/Redis

## Current v2 baseline
- Metadata: SQLite
- Artifacts/logs: filesystem `/srv/odyssey/data/openfactory/jobs`

## Adapter interfaces
- `JobStore`: create/update/get/list
- `CheckpointStore`: save/load latest by job/stage
- `ArtifactStore`: write/read/list artifact files

## Postgres migration plan
1. implement `PostgresJobStore` and `PostgresCheckpointStore`
2. run dual-write in shadow mode
3. validate parity
4. switch read path to Postgres
5. retire SQLite

## Redis migration plan (optional queue/checkpoint cache)
- use Redis streams for queue events and retry scheduling
- keep durable system-of-record in Postgres

## No-downtime strategy
- feature flags per adapter
- backwards-compatible schemas
- one-way migration script with verification report
