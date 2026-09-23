# Envoltorio fino: cada objetivo delega en `uv run` (backend) o `deno task` (frontend).
# No dupliques comandos aquí: ver AGENTS.md §2.

SHELL := /bin/sh

BACKEND := backend
FRONTEND := frontend

.PHONY: help db dev test lint fmt migrate seed openapi check \
	frontend-dev frontend-build frontend-check frontend-test frontend-lint frontend-fmt

help:
	@echo "Objetivos disponibles:"
	@echo "  db             Levanta Postgres con docker compose"
	@echo "  dev            Levanta Postgres y la API en modo desarrollo"
	@echo "  test           Tests del backend"
	@echo "  lint           Formato (check), lint y contratos de import del backend"
	@echo "  fmt            Aplica formato y correcciones automáticas al backend"
	@echo "  migrate        Aplica las migraciones de Alembic"
	@echo "  seed           Siembra los datos canónicos"
	@echo "  openapi        Regenera el cliente TypeScript desde OpenAPI"
	@echo "  frontend-dev   Levanta el frontend (Vite) en modo desarrollo"
	@echo "  frontend-build Build de la SPA"
	@echo "  frontend-check Typecheck del frontend (sync + deno check + svelte-check)"
	@echo "  frontend-test  Tests del frontend (Deno + Vitest)"
	@echo "  frontend-lint  Formato (check) y lint del frontend"
	@echo "  frontend-fmt   Aplica formato al frontend (incluye .svelte)"

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

openapi:
	cd $(BACKEND) && uv run python -m scripts.export_openapi
	cd $(FRONTEND) && deno task openapi

frontend-dev:
	cd $(FRONTEND) && deno task dev

frontend-build:
	cd $(FRONTEND) && deno task build

frontend-check:
	cd $(FRONTEND) && deno task sync && deno task check

frontend-test:
	cd $(FRONTEND) && deno task test && deno task test:unit

frontend-lint:
	cd $(FRONTEND) && deno fmt --check && deno lint

frontend-fmt:
	cd $(FRONTEND) && deno task fmt

check: lint test