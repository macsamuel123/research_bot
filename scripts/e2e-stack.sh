#!/usr/bin/env bash
# Full-stack e2e: api (fake integrations, test DB) + Next dev server, then the Playwright
# `stack` project through the Next proxy. Both servers are always stopped, even on failure.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PORT="${E2E_API_PORT:-8001}"
WEB_PORT="${E2E_WEB_PORT:-3001}"

export APP_ENV=test
export INTEGRATIONS_MODE=fake
export WORKER_ENABLED=false
export DATABASE_URL="${TEST_DATABASE_URL:-postgresql+psycopg://research:research@127.0.0.1:5433/research_test}"
export ANTHROPIC_API_KEY=e2e-dummy-anthropic-key
export ANTHROPIC_MODEL=claude-sonnet-5-5
export TAVILY_API_KEY=e2e-dummy-tavily-key
export TELEGRAM_BOT_TOKEN=e2e-dummy-telegram-token
export OWNER_CHAT_ID=1
# Dummy test-only owner password; its argon2 hash is computed below (never a real secret).
export E2E_OWNER_PASSWORD="${E2E_OWNER_PASSWORD:-e2e-owner-password}"
export SESSION_SECRET=e2e-dummy-session-secret
export PUBLIC_BASE_URL="http://127.0.0.1:${WEB_PORT}"
export RUN_BUDGET_CENTS=50
export RUN_MAX_SEARCH_CALLS=8
export TRUSTED_PROXY_CIDRS=127.0.0.1/32
export NEXT_PUBLIC_USE_MOCKS=0

API_PID=""
WEB_PID=""

stop_group() {
  local pid="$1"
  [[ -n "$pid" ]] || return 0
  # Each server runs in its own session/process group (setsid), so kill the whole group.
  kill -TERM -- "-$pid" 2>/dev/null || true
  for _ in $(seq 1 50); do
    kill -0 -- "-$pid" 2>/dev/null || return 0
    sleep 0.1
  done
  kill -KILL -- "-$pid" 2>/dev/null || true
}

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  stop_group "$WEB_PID"
  stop_group "$API_PID"
  wait 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT INT TERM

wait_for() {
  local url="$1" seconds="$2" name="$3"
  local deadline=$((SECONDS + seconds))
  until curl -fsS -o /dev/null "$url"; do
    if ((SECONDS >= deadline)); then
      echo "e2e-stack: $name did not become ready at $url within ${seconds}s" >&2
      exit 2
    fi
    sleep 1
  done
}

OWNER_PASSWORD_HASH="$(cd "$ROOT/api" && uv run python -c \
  'import sys; from app.auth.password import hash_password; print(hash_password(sys.argv[1]))' \
  "$E2E_OWNER_PASSWORD")"
export OWNER_PASSWORD_HASH

echo "e2e-stack: ensuring test database exists"
(cd "$ROOT/api" && uv run python -m app.testdb "$DATABASE_URL")
(cd "$ROOT/api" && uv run alembic upgrade head)

echo "e2e-stack: starting api on :$API_PORT"
(cd "$ROOT/api" && exec setsid uv run uvicorn app.main:create_app --factory \
  --host 127.0.0.1 --port "$API_PORT") &
API_PID=$!

echo "e2e-stack: starting web on :$WEB_PORT"
(cd "$ROOT/web" && API_INTERNAL_URL="http://127.0.0.1:${API_PORT}" exec setsid pnpm dev \
  --hostname 127.0.0.1 --port "$WEB_PORT") &
WEB_PID=$!

wait_for "http://127.0.0.1:${API_PORT}/health" 60 api
wait_for "http://127.0.0.1:${WEB_PORT}/" 120 web

echo "e2e-stack: running tests"
set +e
STACK_BASE_URL="http://127.0.0.1:${WEB_PORT}" bash -c \
  "${E2E_STACK_CMD:-cd \"$ROOT/web\" && pnpm exec playwright test --project=stack}"
status=$?
set -e
exit "$status"
