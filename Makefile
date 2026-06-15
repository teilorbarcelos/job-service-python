.PHONY: setup dev test coverage lint format typecheck check sonar clean
.PHONY: infra-up infra-down generate-job

ENVIRONMENT ?= development

setup:
	python3 -m venv venv
	./venv/bin/pip install -r requirements.txt
	./venv/bin/pip install ruff mypy pytest pytest-asyncio pytest-cov pytest-mock coverage

dev:
	@echo "🚀 Starting job runner (foreground)..."
	./venv/bin/python -m src.main

test:
	@echo "🧪 Running tests..."
	./venv/bin/pytest

coverage:
	@echo "📊 Generating coverage report (fail under 100%)..."
	./venv/bin/pytest --cov=src --cov-report=xml --cov-report=term-missing --cov-fail-under=100

lint:
	@echo "🧹 Linting with ruff..."
	./venv/bin/ruff check src/ tests/

format:
	@echo "🎨 Formatting with ruff..."
	./venv/bin/ruff format src/ tests/

typecheck:
	@echo "🔍 Typechecking with mypy..."
	./venv/bin/mypy src/

check: lint typecheck test

sonar:
	@echo "📡 Running SonarQube scanner..."
	sonar-scanner

# Exemplo: make generate-job name=CleanupOldRecords
generate-job:
	@echo "🏗️  Generating job CleanupOldRecords..."
	@echo "Crie manualmente src/jobs/CleanupOldRecordsJob.py estendendo BaseJob e registre em src/jobs/register_jobs.py"

infra-up:
	@echo "🐳 Subindo infra local (PG + Redis + RabbitMQ)..."
	docker compose -f docker-compose.infra.yml up -d

infra-down:
	@echo "🛑 Derrubando infra local..."
	docker compose -f docker-compose.infra.yml down

clean:
	rm -rf venv
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -f coverage.xml
