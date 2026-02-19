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
	$(COMPOSE) exec -T api python -m py_compile api/main.py
	$(COMPOSE) exec -T worker python -m py_compile worker/main.py

integration:
	curl -fsS http://127.0.0.1:8080/openapi.json | grep -q '"/v1/jobs"'
	curl -fsS http://127.0.0.1:8080/openapi.json | grep -q '"/v1/jobs/{job_id}/cancel"'
	curl -fsS http://127.0.0.1:8080/openapi.json | grep -q '"/v1/jobs/{job_id}/artifacts"'

smoke:
	./scripts/smoke_deterministic.sh

install-watchdog:
	./scripts/install_systemd_watchdog.sh
