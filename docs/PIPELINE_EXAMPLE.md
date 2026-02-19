# Pipeline Example (Worked Run)

Input job:
`Create hello-world FastAPI with /health and one test; ensure GitHub Actions tests passes.`

## Stage 1 output snippet (`SPEC.md`)
- Scope: generate minimal app with `/health` endpoint and one unit test
- Non-goals: auth, database, deployment
- Acceptance:
  - `pytest` green
  - CI check `tests` green
  - README includes run/test commands

## Stage 3 tickets
1. `TICKETS/0001-scaffold.md` create app skeleton and dependencies
2. `TICKETS/0002-health-endpoint.md` add `/health` implementation
3. `TICKETS/0003-tests.md` add unit test and CI workflow

## Stage 4 sample patch
- Files touched:
  - `app/main.py`
  - `tests/test_health.py`
  - `.github/workflows/tests.yml`

## Stage 6 evidence
- Draft PR created: `https://github.com/ORG/REPO/pull/123`
- Required check `tests`: `success`

## Stage 7 final artifacts summary
- `FINAL_SUMMARY.md`: app behavior + run instructions
- `TEST_REPORT.md`: local test output + CI URL
- `SECURITY_NOTES.md`: guardrails used during run
