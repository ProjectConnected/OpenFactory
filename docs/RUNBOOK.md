# OpenFactory Runbook

## Canonical locations
- Repo: `/srv/odyssey/openfactory/OpenFactory`
- Secrets: `/srv/odyssey/secrets`
- Workspaces: `/srv/odyssey/workspaces`
- Data/DB/backups: `/srv/odyssey/data`

## Daily operations
```bash
cd /srv/odyssey/openfactory/OpenFactory
make doctor
make logs
```

## Start / restart / stop
```bash
sudo systemctl restart openfactory.service
sudo systemctl stop openfactory.service
sudo systemctl start openfactory.service
```

Manual compose fallback:
```bash
cd /srv/odyssey/openfactory/OpenFactory
make restart
```

## Health verification
```bash
cd /srv/odyssey/openfactory/OpenFactory
make doctor
curl -fsS http://127.0.0.1:8080/openapi.json | grep -q '"/v1/jobs"'
curl -fsS http://100.102.56.104:8080/openapi.json | grep -q '"/v1/jobs"'
```

## Logs
- Service logs: `sudo journalctl -u openfactory.service -n 200 --no-pager`
- Watchdog logs: `sudo journalctl -u openfactory-watchdog.service -n 200 --no-pager`
- Container logs: `cd /srv/odyssey/openfactory/OpenFactory && make logs`

## Recovery Routine
1. `cd /srv/odyssey/openfactory/OpenFactory && make doctor`
2. If any FAIL: `sudo systemctl restart openfactory.service`
3. Re-run: `make doctor`
4. If API path check fails, inspect:
   - `sudo journalctl -u openfactory.service -n 200 --no-pager`
   - `docker compose -f docker-compose.pat.yml ps`
5. If worker token/GitHub auth fails:
   - `sudo chown root:root /srv/odyssey/secrets/github_pat.txt`
   - `sudo chmod 600 /srv/odyssey/secrets/github_pat.txt`
   - `sudo systemctl restart openfactory.service`
6. If still broken, restore backup:
   - `/srv/odyssey/data/backups/openfactory-pre-cleanup.tar.gz`

## Security notes
- GitHub PAT read path inside worker container: `/run/secrets/github_pat`
- Do **not** loosen secret file permissions.
- Keep `/srv/odyssey/secrets/*.txt` as `root:root` and mode `600`.
