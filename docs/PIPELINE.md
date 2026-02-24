# OpenFactory Autonomous Pipeline (PR1 skeleton)

This document defines the stage contract for the OpenFactory upgrade.  
PR1 delivers graph/state/docs only and preserves existing `/v1/jobs` behavior.

## Required DONE definition
A run can be marked `done` **only** when:
1. Required CI check context `tests` is `success`
2. PR URL exists
3. Artifacts/log evidence are written under `/srv/odyssey/data/openfactory/jobs/<job_id>/`

## Stage contract

### Stage 0: PREFLIGHT
Validate:
- service/runtime readiness
- secrets presence
- coder provider availability (deferred to PR2 wiring)
- auth/check discovery
- disk/workspace health

Artifacts:
- `PREFLIGHT_REPORT.md`

### Stage 1: SPEC
Create and freeze:
- `SPEC.md`
- `SPEC.json`

Must include scope, non-goals, assumptions, acceptance criteria.

### Stage 2: ARCH
Create:
- `ARCHITECTURE.md`

### Stage 3: TICKETS
Create:
- `TICKETS/0001-*.md` files with goal/files/allowed commands/tests/done

### Stage 4: IMPLEMENT_LOOP
Per ticket (retry <=3):
- generate patch
- apply patch
- run gates
- commit/push

### Stage 5: INTEGRATION
Run constrained integration path and write:
- `INTEGRATION_REPORT.md`

### Stage 6: PR_CI_GATE
- open draft PR
- wait for required check `tests`
- bounded CI fix loop (retry <=2)

### Stage 7: RELEASE
Generate:
- `FINAL_SUMMARY.md`
- `RUNBOOK.md`
- `TEST_REPORT.md`
- `SECURITY_NOTES.md`
- `pipeline.mmd`

## Resumability
Pipeline state is checkpointed per stage and can resume from latest successful stage.

## Mermaid source
`docs/pipeline.mmd` is generated via:

```bash
python3 scripts/generate_pipeline_mmd.py
```
