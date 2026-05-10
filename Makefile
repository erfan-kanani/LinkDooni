DOCKER ?= docker
COMPOSE_FILE ?= docker-compose.yml

.PHONY: install run lint format test migrate revision db-up db-down db-logs db-test-create

install:
	uv sync --dev

run:
	uv run linkdooni

lint:
	uv run ruff check .

format:
	uv run ruff format .

test:
	uv run pytest

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision --autogenerate -m "$(m)"

db-up:
	$(DOCKER) compose -f $(COMPOSE_FILE) up -d db

db-down:
	$(DOCKER) compose -f $(COMPOSE_FILE) down

db-logs:
	$(DOCKER) compose -f $(COMPOSE_FILE) logs -f db

db-test-create:
	$(DOCKER) exec linkdooni-postgres psql -U linkdooni -d linkdooni -c "CREATE DATABASE linkdooni_test;" || true
