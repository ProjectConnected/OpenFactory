# OpenFactory v2 Audit (2026-02-19 UTC)

## Scope
Audit of current production deployment at  against the requested **AI Software Factory v2** pipeline and guardrails.

## Current State (Observed)
- Repo + services are operational on canonical path and compose file ().
- Services up: ,  (docker compose).
- Health baseline currently passes:
  -  exits 0
  -  contains 
- Branch protection is enabled on  with required status check context .
- Secret handling is already improved vs earlier hack:
  - worker/API read secrets from 
  - no token value printing in doctor/normal logs.
- Co-author support exists via env vars (, ).

## Gap Analysis vs v2 Requirements

### 1) API Surface (required: create/status/artifacts/cancel)
**Exists:**
- 
- 

**Missing:**
-  (or equivalent)
-  (or equivalent)
- richer status model with per-stage state

### 2) Orchestrated Pipeline / LangGraph
**Exists:**
- Single-loop worker that:
  - claims queued job
  - clones repo + applies template
  - commits/pushes
  - opens draft PR
  - waits for check-runs and sets simple ci state

**Missing:**
- LangGraph orchestrator with explicit stages 0..7
- checkpointed state machine + resumability
- stage outputs (, , , tickets, integration report, release artifacts)
- deterministic retry policy per stage and CI-fix loop semantics from spec

### 3) Worker Executor Hardening
**Exists:**
- containerized worker
- read-only rootfs, tmpfs, dropped caps, no-new-privileges

**Missing / needs tightening:**
- explicit command allowlist framework (deny-by-default execution API)
- per-ticket sandbox execution contract
- structured per-command audit logs and exit metadata
- explicit non-root assertion and runtime checks inside worker

### 4) CI Gate Semantics
**Exists:**
- PR-based flow; waits for check runs; required check  configured in branch protection.

**Missing:**
- local gate sequence (, ) before PR gate
- CI failure remediation loop with bounded retries and fetched failure evidence
- deterministic gate contract: job done only when 

### 5) Artifacts + Auditability
**Exists:**
- sqlite job metadata fields: id/status/pr_url/ci_status/error/timestamps

**Missing:**
- per-job artifact directory model under  (logs, patches, reports)
- trace IDs and stage-level logs
- final report bundle (, , , ) generated per job

### 6) Spec/Tickets Discipline
**Missing:**
- Spec freeze docs and schemas
- ticket files () with allowed commands/tests/done criteria
- implementation loop bounded by ticket constraints

### 7) Model Config + Fail-Fast
**Missing:**
- persisted model execution metadata per run (provider base_url, model id, temperature/max_tokens)
- explicit fail-fast behavior when provider unavailable (currently no model provider integration contract)

### 8) Smoke Repo Policy
**Observed:** org currently has , , .

**Required delta:**
- keep only one smoke example repo ()
- delete others if permissions allow; otherwise report inability.

## Reliability Constraints for Upgrade Plan
- Keep current API/worker behavior functional while layering v2 pipeline.
- Prefer SQLite-backed interfaces now, with storage abstractions for Postgres/Redis migration later.
- Implement in at most 3 PRs:
  1. orchestrator + pipeline docs + schemas
  2. worker hardening + allowlist + secret enforcement
  3. doctor/watchdog + deterministic smoke harness

## Proposed File/Module Additions (incremental)
-  (LangGraph state machine)
-  (typed state + checkpoints)
-  (stage handlers 0..7)
-  (artifact + metadata interfaces; sqlite impl now)
-  (allowlisted command runner)
- , 
- 
- API additions for artifacts/cancel and richer status payloads

## Immediate Next Step
Create PR1 () without breaking existing  baseline behavior.
