# OpenFactory Upgrade Audit (post PR2/PR3 pass)

Date: 2026-02-24 UTC  
Repo: `ProjectConnected/OpenFactory`

## Capability status

### Implemented
- `/v1/jobs` API remains backward compatible (`create/status/cancel/artifacts`).
- Worker guardrails now include:
  - non-root runtime assertion
  - centralized deny-by-default command policy
  - shell metacharacter blocking
  - banned binaries (`curl`, `wget`, destructive system commands)
  - protected branch push block
  - log redaction
- Headless coder provider contract implemented:
  - input: `repo_path + ticket + context`
  - output: unified diff patch text only
  - default provider: `gemini_cli`
  - fail-fast readiness/auth checks
- Implement loop now applies generated unified diff via controlled `git apply --check` + `git apply`.
- Constrained integration runner added for compose actions (`up/down/ps/logs`) with fixed canonical compose path.
- Doctor/self-heal checks expanded to include Gemini availability + non-interactive probe.
- Deterministic smoke harness now persists job/evidence artifacts (`SMOKE_SUBMIT_RESPONSE.json`, `SMOKE_LAST_STATUS.json`, `SMOKE_EVIDENCE.txt`).

### Still intentionally limited
- LangGraph orchestrator graph/state remains a skeleton model (documented stage contract), while runtime execution continues through worker pipeline logic.
- Full persisted typed orchestration state as single source of truth is not yet the runtime authority.

## Security posture notes
- No provider-side file writes: coder provider returns patch text only.
- Command execution remains in worker executor path only.
- Integration command surface is constrained to explicit compose actions.

## Verification targets
- `make doctor`
- `/openapi.json` contains `/v1/jobs`
- deterministic smoke job produces PR URL + CI success evidence artifacts
