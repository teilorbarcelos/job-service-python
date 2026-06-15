# Makefile to simplify project commands

.PHONY: setup dev test coverage generate storage-driver clean stop infra-up infra-down
.PHONY: metrics-up metrics-stop metrics-down metrics-logs
.PHONY: lint format typecheck security shell psql redis-cli logs db-migrate db-upgrade db-status
.PHONY: install-dev deps-update check sonar

setup:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt

install-dev:
	./venv/bin/pip install ruff mypy bandit safety

dev:
	./venv/bin/uvicorn src.main:app --reload --host 0.0.0.0 --port 8888

test:
	./venv/bin/pytest

coverage:
	./venv/bin/pytest --cov=src --cov-report=xml --cov-report=term-missing tests/

lint:
	./venv/bin/ruff check src/ tests/

check: lint typecheck test

format:
	./venv/bin/ruff format src/ tests/

typecheck:
	./venv/bin/mypy src/ --no-error-summary

sonar:
	sonar-scanner

security:
	./venv/bin/bandit -r src/ -x venv,tests,migrations
	./venv/bin/safety check --bare

generate:
	./venv/bin/python3 scripts/generate_module.py $(name)

storage-driver:
	./venv/bin/python3 scripts/install_storage.py $(name)

infra-up:
	docker compose up -d db redis rabbitmq

infra-down:
	docker compose down

metrics-up:
	docker compose -f docker-compose.metrics.yml up -d

metrics-stop:
	docker compose -f docker-compose.metrics.yml stop

metrics-down:
	docker compose -f docker-compose.metrics.yml down

metrics-logs:
	docker compose -f docker-compose.metrics.yml logs -f

db-migrate:
	./venv/bin/python3 -m alembic revision --autogenerate -m "auto_migration"

db-upgrade:
	./venv/bin/python3 -m alembic upgrade head

db-status:
	./venv/bin/python3 -m alembic current

shell:
	./venv/bin/python3

psql:
	PGPASSWORD=$$(grep POSTGRES_PASSWORD .env | cut -d= -f2) psql -h localhost -U $$(grep POSTGRES_USER .env | cut -d= -f2) -d $$(grep POSTGRES_DB .env | cut -d= -f2)

redis-cli:
	redis-cli -h localhost -p 6379

logs:
	docker compose logs -f

deps-update:
	./venv/bin/pip install --upgrade -r requirements.txt

clean:
	rm -rf venv
	rm -f test.db
	find . -type d -name "__pycache__" -exec rm -rf {} +

stop: infra-down
