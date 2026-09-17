# Envoltorio fino: cada objetivo delega en `uv run` (backend) o `deno task` (frontend).
# No dupliques comandos aquí: ver AGENTS.md §2.

SHELL := /bin/sh

BACKEND := backend
FRONTEND := frontend

.PHONY: help db dev test lint fmt migrate seed openapi check

help:
	@echo "Objetivos disponibles:"
	@echo "  db         Levanta Postgres con docker compose"
	@echo "  dev        Levanta Postgres y la API en modo desarrollo"
	@echo "  test       Tests del backend"
	@echo "  lint       Formato (check), lint y contratos de import del backend"
	@echo "  fmt        Aplica formato y correcciones automáticas al backend"
	@echo "  migrate    Aplica las migraciones de Alembic"
	@echo "  seed       Siembra los datos canónicos"
	@echo "  openapi    Regenera el cliente TypeScript desde OpenAPI"

db:
	docker compose up -d postgres

dev: db
	cd $(BACKEND) && uv run uvicorn app.main:app --reload

test:
	cd $(BACKEND) && uv run pytest

lint:
	cd $(BACKEND) && uv run ruff format --check .
	cd $(BACKEND) && uv run ruff check .
	cd $(BACKEND) && uv run lint-imports

fmt:
	cd $(BACKEND) && uv run ruff format .
	cd $(BACKEND) && uv run ruff check --fix .

migrate:
	cd $(BACKEND) && uv run alembic upgrade head

seed:
	cd $(BACKEND) && uv run python -m app.seed

# El frontend se andamia en la Fase 4; hasta entonces no hay `deno task` que invocar.
openapi:
	@echo "El cliente API se genera en la Fase 3 (ver DEVELOPMENT_PLAN.md §5)."

check: lint test