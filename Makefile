COMPOSE = docker compose -f docker-compose.pat.yml

.PHONY: up down restart logs doctor test integration smoke install-watchdog

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) down
	$(COMPOSE) up -d --build

logs:
	$(COMPOSE) logs -f --tail=200 api worker

doctor:
	./scripts/doctor.sh

test:
	$(COMPOSE) exec -T api python -c "import api.main"
	$(COMPOSE) exec -T worker python -c "import worker.main"

integration:
	for i in $$(seq 1 20); do curl -fsS http://127.0.0.1:8080/openapi.json >/dev/null && break; sleep 1; done
	curl -fsS http://127.0.0.1:8080/openapi.json | grep -q '"/v1/jobs"'
	curl -fsS http://127.0.0.1:8080/openapi.json | grep -q '"/v1/jobs/{job_id}/cancel"'
	curl -fsS http://127.0.0.1:8080/openapi.json | grep -q '"/v1/jobs/{job_id}/artifacts"'

smoke:
	./scripts/smoke_deterministic.sh

install-watchdog:
	./scripts/install_systemd_watchdog.sh
