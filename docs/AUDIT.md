# OpenFactory Upgrade Audit (PR1 baseline)

Date: 2026-02-24 UTC  
Repo: `ProjectConnected/OpenFactory`

## Mission Target (summary)
Upgrade the existing OpenFactory from template+PR automation into a checkpointed autonomous factory with:
- LangGraph stage orchestrator
- headless coder provider contract (Gemini CLI; patch-only)
- sandboxed executor with deny-by-default allowlist
- CI-gated completion where `tests=success` is the only DONE state

## Current Capability Snapshot

### Already present
- `/v1/jobs` create/status API exists and is functional in current code path (`api/main.py`).
- Job cancellation and artifact listing endpoints also exist:
  - `/v1/jobs/{job_id}/cancel`
  - `/v1/jobs/{job_id}/artifacts`
- Worker already enforces several guardrails:
  - non-root assertion (`ensure_non_root`)
  - deny-by-default command tuple allowlist
  - protected branch push block (origin main/master)
  - artifact log token redaction
- CI wait loop exists with required check context support (`OPENFACTORY_REQUIRED_CHECK`, default `tests`).
- Artifact checkpoint files are already being written under `/data/openfactory/jobs/<job_id>/checkpoints`.
- `make doctor` exists and checks service health/openapi/auth basics.

### Gap vs requested target

#### Orchestration depth (LangGraph)
- `worker/orchestrator/*` exists but is a skeleton not wired into runtime execution.
- Stage naming does not yet map cleanly to required Stage 0..7 contract.
- Resumability exists only partially through ad hoc checkpoint artifacts; no typed persisted orchestration state is currently authoritative.

#### Headless coder provider (Gemini CLI patch-only)
- No strict provider interface yet (input repo+ticket+context -> unified diff output).
- No Gemini CLI provider implementation.
- No fail-fast auth/readiness checks for Gemini CLI.

#### Executor hardening requirements
- Existing allowlist exists, but command policy still allows flows outside the requested strict ticket-scoped command contract.
- Explicit bans for shell chaining/pipes/redirection are not centrally enforced as a reusable execution policy module.
- Integration command path is not yet isolated to a dedicated constrained integration-runner with the exact compose allowlist.

#### CI gate semantics
- CI polling exists, but DONE contract and retry semantics are not fully bound to deterministic smoke evidence requirements.
- CI evidence and logs are partially captured; deterministic smoke harness requirements need formalization.

#### Doctor/self-heal contract
- Current doctor checks service state/openapi/secrets/auth.
- Missing explicit Gemini CLI non-interactive provider probe.
- Missing explicit worker restart-loop health assertion tied to orchestrator state.

## PR Plan Alignment

### PR1 (this step)
- Add/normalize orchestrator skeleton + typed state schema + checkpoint metadata model.
- Add pipeline documentation and mermaid diagram generation for the required stage flow.
- Keep `/v1/jobs` path backward compatible and untouched functionally.

### PR2 (deferred)
- Implement `coder_provider=gemini_cli` (patch-only contract) and secure patch-apply execution loop.

### PR3 (deferred)
- Add deterministic smoke harness, CI fix-loop evidence capture improvements, and constrained integration-runner flow.

## Non-goals in PR1
- No production switch-over of worker runtime to new orchestrator execution.
- No Gemini execution logic.
- No destructive repo actions.
