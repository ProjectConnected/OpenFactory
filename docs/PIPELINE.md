# OpenFactory v2 Pipeline

This document defines the production pipeline contract for OpenFactory v2.

## Hard definition of done
A job is `done` only when all are true:
1. preflight and local gates passed
2. PR exists
3. CI required check context `tests` is `success`

## Stage flow (LangGraph)

### Stage 0: PREFLIGHT
Checks:
- Docker reachable
- compose file present and services discoverable
- secrets files reachable by containerized worker
- git auth reachable
- branch protection required check contexts discovered (`tests` must exist)

Output artifact: `PREFLIGHT_REPORT.md`

### Stage 1: INTAKE -> SPEC FREEZE
Input task is transformed to:
- `SPEC.md`
- `SPEC.json`

Both include:
- scope
- non-goals
- assumptions
- acceptance criteria
- constraints
- risk/threat notes

If blocked, ask exactly one clarification question.

### Stage 2: ARCHITECTURE
Generate `ARCHITECTURE.md`:
- components
- data flow
- interfaces
- storage
- test strategy

### Stage 3: TICKET PLANNING
Generate `TICKETS/0001-*.md` etc.
Each ticket includes:
- goal
- files touched
- commands allowed
- tests required
- done criteria

### Stage 4: IMPLEMENT LOOP (per ticket)
For each ticket:
- create branch/worktree
- implement
- run allowlisted commands only
- auto-fix loop with max retries (default 3)
- emit `PATCH.diff`

Outputs:
- ticket patch
- command logs
- test logs

### Stage 5: INTEGRATION
- compose up
- run integration tests

Output: `INTEGRATION_REPORT.md`

### Stage 6: PR + CI GATE
- open draft PR
- wait for required check `tests`
- if failure: fetch CI evidence, patch, push retry (default max 2)
- terminal statuses: `done` only when `tests=success`, otherwise `ci_failed`

Output:
- PR URL
- CI conclusion

### Stage 7: RELEASE ARTIFACTS
Generate:
- `FINAL_SUMMARY.md`
- `RUNBOOK.md`
- `TEST_REPORT.md`
- `SECURITY_NOTES.md`

Persist all artifacts on disk under `/srv/odyssey/data/openfactory/jobs/<job_id>/`.

## Checkpointing + resumability
The orchestrator state is persisted after each stage. On worker restart:
- reload latest checkpoint
- continue from next incomplete stage

## Storage contracts
Current implementation target: SQLite + filesystem.
Future: Postgres/Redis via adapters (see `docs/MIGRATION_SQLITE_TO_PG_REDIS.md`).

## Security guardrails
- execution only in worker container, non-root
- deny-by-default allowlist for commands
- secrets from `/run/secrets/*`
- never write secrets to repo or artifacts
- no direct pushes to protected main by jobs
