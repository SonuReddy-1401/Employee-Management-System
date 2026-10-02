.PHONY: up up-dev down logs test coverage e2e contract-test chaos load

up:
	docker compose up -d --wait

up-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --wait

down:
	docker compose down -v

logs:
	docker compose logs -f

test:
	pytest services/gateway services/auth services/employee services/leave services/payroll services/notification libs/common -v

coverage:
	python scripts/coverage.py

e2e:
	pytest tests/e2e -v

contract-test:
	pytest tests/contract -v

chaos:
	python -m pytest tests/chaos -v -m chaos -s

load:
	python scripts/load.py



