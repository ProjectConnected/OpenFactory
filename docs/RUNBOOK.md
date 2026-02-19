# OpenFactory Runbook

## Canonical paths
- Repo: `/srv/odyssey/openfactory/OpenFactory`
- Secrets: `/srv/odyssey/secrets`
- Data/artifacts: `/srv/odyssey/data/openfactory/jobs`

## Core commands
```bash
cd /srv/odyssey/openfactory/OpenFactory
make restart
make doctor
make test
make integration
make smoke
make logs
```

## Health expectations
- `make doctor` exits 0
- `curl -fsS http://127.0.0.1:8080/openapi.json | grep -q '"/v1/jobs"'`
- worker can read `/run/secrets/github_pat`
- branch protection required check includes `tests`

## Recovery routine
1. `make doctor`
2. If fail, `make restart`
3. Re-run `make test && make integration`
4. Run `make smoke`
5. If still failing: inspect `make logs` and `journalctl -u openfactory.service -n 200`

## Watchdog
Install/update watchdog units from repo templates:
```bash
cd /srv/odyssey/openfactory/OpenFactory
make install-watchdog
systemctl status openfactory-watchdog.timer
```

Watchdog action:
- every 60s check `/openapi.json` has `/v1/jobs`
- restart `openfactory.service` on failure

## Job artifacts
Per-job output is written under:
`/srv/odyssey/data/openfactory/jobs/<job_id>/`

Expected files include:
- `PREFLIGHT_REPORT.md`
- `SPEC.md`, `SPEC.json`
- `ARCHITECTURE.md`
- `TICKETS/*`
- `FINAL_SUMMARY.md`
- `TEST_REPORT.md`
- `SECURITY_NOTES.md`
- `logs/*.log`
