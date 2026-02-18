COMPOSE = docker compose -f docker-compose.pat.yml

.PHONY: up down restart logs doctor

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
