SHELL := /bin/bash

# Dev defaults for `make db-up` only (compose.yaml validates without them).
export POSTGRES_USER ?= research
export POSTGRES_PASSWORD ?= research
export POSTGRES_DB ?= research

COMPOSE_DEV := docker compose -f compose.yaml -f compose.dev.yaml

.PHONY: install db-up db-down dev lint typecheck test test-api test-web e2e-stack build

install:
	cd api && uv sync
	cd web && pnpm install --frozen-lockfile && pnpm exec playwright install chromium

db-up:
	$(COMPOSE_DEV) up -d --wait postgres

db-down:
	$(COMPOSE_DEV) down

dev:
	@trap 'kill 0' EXIT INT TERM; \
	(cd api && uv run uvicorn app.main:create_app --factory --reload --port 8000) & \
	(cd web && API_INTERNAL_URL=http://127.0.0.1:8000 pnpm dev --port 3000) & \
	wait

lint:
	cd api && uv run ruff check . && uv run ruff format --check .
	cd web && pnpm lint

typecheck:
	cd api && uv run mypy --strict app
	cd web && pnpm typecheck

test: test-api test-web e2e-stack

test-api:
	@echo "==> test-api"
	cd api && uv run pytest

test-web:
	@echo "==> test-web"
	cd web && pnpm test && pnpm test:e2e

e2e-stack:
	@echo "==> e2e-stack"
	./scripts/e2e-stack.sh

build:
	cd web && pnpm build
	docker compose -f compose.yaml build
