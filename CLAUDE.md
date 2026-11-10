# CLAUDE.md

## Project
Research Bot is a single-owner personal research assistant. The owner submits a topic. A Claude agent searches the web through Tavily and saves cited, deduplicated findings into a chat thread at `/r/<id>`. Optional watches re-run the research on a schedule (6h, daily or weekly), and watch runs with new findings send a Telegram alert. Other bots use the same features, plus a ranked-themes digest, through an API-key-protected `/api/v1`. Requirement IDs (R1–R26) are defined in PLAN.md "Requirements traceability".

**Users:**
- **The owner:** the only human. Uses the web UI with a password login, mostly on a phone, and the Telegram bot from `OWNER_CHAT_ID`.
- **API clients:** other bots, using a Bearer key.
- **Everyone else:** gets 401, and the Telegram bot silently ignores them.

**Stack:**
- **Backend:** Python 3.12, FastAPI, Pydantic v2 and pydantic-settings, SQLAlchemy 2 (sync ORM, psycopg3), Alembic, argon2-cffi, httpx, the Anthropic Python SDK, Tavily over httpx, and python-telegram-bot v21 (long polling). Dependencies are managed with uv.
- **Frontend:** Next.js App Router, TypeScript strict, Tailwind, dark mode by default, managed with pnpm.
- **Tests:** pytest, httpx TestClient, respx, Hypothesis and pytest-socket on the backend. Vitest with Testing Library and Playwright on the frontend.
- **DB:** PostgreSQL 16.
- **Scheduling:** a DB-polling worker inside the api process.
- **Hosting:** Docker Compose (`api`, `web`, `postgres`, `bot`) on an Azure VM, reachable only over Tailscale. Next.js rewrites proxy `/api`, `/docs` and `/openapi.json` to FastAPI, so the session cookie is same-origin.

## Commands
<!-- For humans and the coder. The orchestrator auto-detects these; put overrides in orchestrator.yaml. -->
- Install: `make install` (`cd api && uv sync` plus `cd web && pnpm install --frozen-lockfile && pnpm exec playwright install chromium`)
- DB for dev and tests: `make db-up` runs `docker compose -f compose.yaml -f compose.dev.yaml up -d postgres`, which publishes postgres on `127.0.0.1:5433`.
  - Tests use `TEST_DATABASE_URL` (default `postgresql+psycopg://research:research@127.0.0.1:5433/research_test`).
  - `compose.yaml` alone never publishes postgres, and no `compose.override.yaml` may be committed.
- Dev server: `make dev` runs the api on port 8000 (`uv run uvicorn app.main:create_app --factory --reload`) and the web app on port 3000 (`pnpm dev`, with `API_INTERNAL_URL=http://127.0.0.1:8000` and `TRUSTED_PROXY_CIDRS=127.0.0.1/32`).
  - `NEXT_PUBLIC_USE_MOCKS=1 pnpm dev` serves the mock-data UI preview, including `/preview` (phone frame).
- Test: `make test` is the single command the orchestrator runs. It runs:
  - `test-api`: `cd api && uv run pytest`
  - `test-web`: `cd web && pnpm test && pnpm test:e2e`, which is Vitest plus Playwright in mock mode on the `desktop` and `mobile` projects
  - `e2e-stack`: starts the api with `INTEGRATIONS_MODE=fake` and `APP_ENV=test` plus the web dev server, runs the Playwright `stack` project through the Next proxy, then stops both

  `make e2e-stack` proves every criterion marked "full-stack": M3-C8, M6-C6, M7-C6, M9-C7, M9-C8 and the like. From M15 on, `make test` also runs `make smoke` (a compose production-build journey, M15-C7). If an `orchestrator.yaml` overrides the test command, it must still run `make test`.
- Lint: `make lint` (`uv run ruff check . && uv run ruff format --check .` plus `pnpm lint`)
- Typecheck: `make typecheck` (`uv run mypy --strict app` plus `pnpm typecheck`, which runs `tsc --noEmit`)
- Build: `make build` (`pnpm build` plus `docker compose -f compose.yaml build`)
- Migrations: `cd api && uv run alembic revision --autogenerate -m "<msg>"`, `uv run alembic upgrade head`, `uv run alembic check`
- CLI: `uv run python -m app.cli hash-password [--compose] | create-key <name> | list-keys | revoke-key <id>`

## Architecture
```
Makefile  compose.yaml (prod-safe)  compose.dev.yaml (dev DB port)  compose.smoke.yaml  .env.example  .gitignore
api/
  pyproject.toml  uv.lock  alembic.ini  Dockerfile
  alembic/versions/            # one migration per schema change; never edit merged ones
  app/
    main.py                    # create_app(): routers, exception handlers, custom /docs + /openapi.json, lifespan (stale sweep, worker start)
    config.py                  # Settings + NON_SETTINGS_ENV allowlist; the ONLY place env is read
    db.py                      # engine, session dependency
    clock.py                   # Clock protocol + SystemClock + FakeClock; inject wherever time matters
    logging.py                 # setup + SecretRedactingFilter; quiets httpx/httpcore/telegram loggers
    models/                    # SQLAlchemy models (research, message, finding, run, api_key, digest_cache)
    schemas/                   # Pydantic In/Out models (incl. FindingIn validator)
    auth/                      # password.py, session.py, api_keys.py, client_ip.py, rate_limit.py, deps.py (require_owner, require_api_key, require_owner_or_key, PUBLIC_PATHS)
    routers/                   # health, auth, keys, researches, findings, runs, stream (SSE), docs, v1/ (researches, findings, digest, whoami)
    services/                  # business logic shared by routers, bot and worker (researches, findings, runs: open_run/execute/start_background, digest)
    engine/                    # agent.py (run_turn loop), tools.py, budget.py (RunBudget: caps + projection), cost.py, normalize.py, dedupe.py, prompts.py
    worker/                    # slots.py, scheduler.py (tick, claim, stale sweep)
    integrations/              # llm.py, search.py, notifier.py (Protocols), anthropic_llm.py, tavily.py, telegram_notifier.py, fakes.py, factory.py
    bot/                       # __main__.py, handlers.py, callbacks.py (encode/decode), alerts.py (render)
    cli.py
  tests/                       # mirrors app/; conftest.py migrates once per session and truncates all tables between tests
web/
  next.config.ts               # rewrites to API_INTERNAL_URL, compress:false, experimental.proxyTimeout
  src/middleware.ts            # no session cookie → redirect to /login?next=<path>
  src/app/login/  src/app/(app)/layout.tsx (auth gate + sidebar)  src/app/(app)/page.tsx (landing)
  src/app/(app)/r/[id]/page.tsx  src/app/(app)/keys/page.tsx  src/app/preview/
  src/components/              # Sidebar, Drawer, Composer, MessageList, RunStatus, FindingsPanel, WatchSettings, RunHistory, BottomSheet, ConfirmDialog
  src/lib/api/                 # types.ts, client.ts (ApiClient interface + factory), http.ts, mock.ts, sse.ts
  src/lib/format.ts  src/lib/safeNext.ts
  tests/ (Vitest)  e2e/ (Playwright; projects desktop 1280×800 + mobile 390×844 in mock mode, stack for full-stack)  screenshots/
```

**Schema:** All IDs are `bigint generated always as identity`, all times are `timestamptz` (UTC), and child foreign keys use `ON DELETE CASCADE` unless noted. Items marked **(M14 migration only)** are not part of the M2 migration or the M2-C1 comparison.
- **`research`:**
  - `id`, `title text NOT NULL` and `topic text NOT NULL`
  - `created_at NOT NULL DEFAULT now()`
  - `watch_enabled bool NOT NULL DEFAULT false` and `watch_enabled_at NULL`
  - `schedule text NULL` (CHECK `6h|daily|weekly`)
  - `last_run_at NULL`
  - `unread bool NOT NULL DEFAULT false`
  - `last_activity_at NOT NULL DEFAULT now()` (indexed desc)
  - `topic_key text NULL`, indexed **(M14 migration only)**
- **`message`:** `id`, `research_id FK NOT NULL`, `role text NOT NULL` (CHECK `user|assistant`), `content text NOT NULL`, `created_at NOT NULL DEFAULT now()`.
- **`finding`:**
  - `id`, `research_id FK NOT NULL`, `run_id FK NULL` (`ON DELETE SET NULL`)
  - `title text NOT NULL`, `url text NOT NULL` (CHECK `url ~ '^https?://'`), `summary text NOT NULL`, `source text NOT NULL` (hostname)
  - `found_at NOT NULL DEFAULT now()`
  - `url_hash text NOT NULL` (sha256 of the normalized URL), `content_hash text NOT NULL` (sha256 of the normalized title + "\n" + summary), `dedupe_hash text NOT NULL` (sha256 of url_hash + content_hash)
  - `dismissed bool NOT NULL DEFAULT false`
  - UNIQUE on (research_id, dedupe_hash), (research_id, url_hash) and (research_id, content_hash)
- **`run`:**
  - `id`, `research_id FK NOT NULL`
  - `trigger text NOT NULL` (CHECK `chat|watch|telegram|api|digest`), `scheduled_for NULL`
  - `started_at NOT NULL DEFAULT now()`, `finished_at NULL`
  - `status text NOT NULL` (CHECK `running|ok|capped|error`)
  - `cost_cents integer NOT NULL DEFAULT 0`, plus `input_tokens`, `output_tokens`, `search_calls` and `new_findings`, each `integer NOT NULL DEFAULT 0`
  - UNIQUE on (research_id, scheduled_for)
  - partial UNIQUE index `run_one_running_per_research` on (research_id) WHERE status = 'running'
- **`api_key`:** `id`, `name text NOT NULL`, `key_hash text NOT NULL UNIQUE`, `created_at NOT NULL DEFAULT now()`, `revoked_at NULL`.
- **`digest_cache`** **(M14 migration only)**: `id`, `topic_key text NOT NULL`, `days integer NOT NULL`, `body jsonb NOT NULL`, `created_at NOT NULL`. UNIQUE on (topic_key, days).

**Settings** (`app/config.py`):
- **Required, startup fails if missing:**
  - `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL`. The model has no default. `.env.example` has the placeholder `claude-sonnet-5-5`, and the owner checks it against Anthropic's current model list before deploying.
  - `TAVILY_API_KEY`, `DATABASE_URL`, `TELEGRAM_BOT_TOKEN` and `OWNER_CHAT_ID` (int).
  - `OWNER_PASSWORD_HASH` and `SESSION_SECRET`.
  - `PUBLIC_BASE_URL`: an absolute http(s) URL, which must be https when `APP_ENV=production`.
  - `RUN_BUDGET_CENTS` (positive int, 50 recommended) and `RUN_MAX_SEARCH_CALLS` (positive int, 8 recommended).
- **Defaulted:**
  - Environment and integrations: `APP_ENV=development` (`development|test|production`), `INTEGRATIONS_MODE=real` (`real|fake`), `FAKE_LLM_CHUNK_DELAY_MS=0`
  - Worker: `WORKER_ENABLED=true`, `WORKER_TICK_SECONDS=60`
  - Session and login: `SESSION_MAX_AGE_DAYS=30`, `LOGIN_RATE_LIMIT_PER_MIN=5`, `TRUSTED_PROXY_CIDRS=""` (comma list)
  - Run limits: `RUN_MAX_LLM_CALLS=12`, `LLM_MAX_TOKENS=2048`, `RUN_TIMEOUT_SECONDS=180`, `RUN_STALE_AFTER_SECONDS=600` (must be greater than the timeout)
  - Prices, as integer placeholders to be checked against current pricing: `PRICE_INPUT_CENTS_PER_MTOK=300`, `PRICE_OUTPUT_CENTS_PER_MTOK=1500`, `PRICE_SEARCH_CENTS_PER_1K=800`
  - Digest: `DIGEST_SYNTH_RESERVE_CENTS=10` (must be below the budget), `DIGEST_CACHE_HOURS=24`
- **`NON_SETTINGS_ENV`** lists keys that appear in `.env.example` but are not Settings fields: `BIND_ADDR`, `API_INTERNAL_URL`, `NEXT_PUBLIC_USE_MOCKS`, `TEST_DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`.

**Run lifecycle:**
1. Every run starts with `services.runs.open_run()`. It inserts the `running` run row (plus the user message, if any) in one transaction. The partial unique index enforces one running run per research, and a violation raises `Conflict`, which becomes HTTP 409.
2. `services.runs.start_background(research_id, trigger, user_content=None, sink=None)` calls `open_run`, then runs `execute(run_id, sink)` as an asyncio task in the calling process. The task is held in a module-level set until done.
3. The SSE endpoints pass a queue-backed sink and stream from it. On client disconnect the sink is detached and the task keeps running to a terminal status.
4. Runs execute in the api process for `chat`, `watch`, `api` and `digest` runs, and in the bot process for `telegram` runs. Digest runs are awaited synchronously inside the request.
5. `execute` calls `engine.agent.run_turn(research_id, run_id, trigger, sink, budget)`. The engine calls `LLMClient` and `SearchClient` only through `RunBudget`.
6. `GET /api/researches/{id}` exposes `active_run`. The thread polls every 2 s while it is non-null.
7. The stale sweep (on api startup, on bot startup and at every worker tick) marks dead `running` runs as `error`.
8. Watch and telegram runs with new findings call `Notifier`.

**Owner API** (`/api/*` except `/api/v1/*`, session cookie):
- `auth/login|logout|me`
- `keys`, `keys/{id}/revoke`
- `researches`: CRUD, `/{id}/messages` (SSE), `/{id}/respond` (SSE), `/{id}/read`, `/{id}/findings`, `/{id}/runs`
- `findings/{id}/dismiss`

**Client API** (`/api/v1/*`, Bearer key): `researches`, `researches/{id}/findings`, `digest`, `whoami`. `/docs` and `/openapi.json` accept a session or a key (key support from M13).

**SSE events:** `token {text}`, `finding {id,title,url,summary,source,found_at}`, `done {run_id,status,cost_cents,new_findings}`, `error {message}`. They go through the Next rewrite proxy with `compress: false` and `proxyTimeout >= (RUN_TIMEOUT_SECONDS + 30) s`.

**Client IP:** If the TCP peer is in `TRUSTED_PROXY_CIDRS`, the client IP is the rightmost `X-Forwarded-For` entry, which the Next proxy appends. That range is the web container's static IP in compose and `127.0.0.1/32` in dev. Otherwise the client IP is the peer address. Only `auth/client_ip.py` reads `X-Forwarded-For`.

**Watch slots:** `slot = floor(epoch_utc / interval) * interval`, with intervals 6h, 24h and 7d. A watch is due when the current slot is later than `slot(watch_enabled_at)` and no run exists for (research_id, slot).

**Digest:**
1. Compute the `topic_key` (NFKC, lowercase, trim, collapse whitespace) and take a Postgres advisory lock on (topic_key, days).
2. Return the cached body if it is fresh.
3. Otherwise find or create the research, and return 409 if it has a non-digest run `running`.
4. Run one `digest` run. Its research phase is capped at `RUN_BUDGET_CENTS − DIGEST_SYNTH_RESERVE_CENTS`.
5. Make one tool-less synthesis LLM call, projection-checked against the full budget.
6. Fall back to the deterministic host-grouping themes when needed.
7. Upsert the cache row.

**Frontend data:** every backend call goes through the `ApiClient` interface. `NEXT_PUBLIC_USE_MOCKS=1` selects `mock.ts` (deterministic fixtures, simulated streaming and a simulated active run). Otherwise `http.ts` is used.

**Deployment notes:**
- **`PUBLIC_BASE_URL`:** use the Tailscale MagicDNS HTTPS hostname, e.g. `https://research.<tailnet>.ts.net`, served by `tailscale serve` to `127.0.0.1:<web port>`. Then set `BIND_ADDR=127.0.0.1`. Without `tailscale serve`, set `BIND_ADDR` to the VM's Tailscale IP. A bare `http://100.x.y.z` URL is rejected in production, because Telegram may refuse it as a button URL and it breaks the `Secure` cookie.
- **`OWNER_PASSWORD_HASH`:** the argon2 hash contains `$`. Compose interpolation treats `$` as a variable, so put the output of `python -m app.cli hash-password --compose` (every `$` doubled) into the compose `.env`. M15-C6 tests this.
- **Startup order:** the `api` container runs `alembic upgrade head` before uvicorn, and `bot` and `web` wait for `api` to be healthy.

## Invariants (the reviewer blocks merges that break these)
- INV-1: Money is integer cents everywhere.
  - DB cost columns are `integer`, and the `PRICE_*` settings are `int`.
  - `engine/cost.py` uses only int arithmetic with a single ceiling division.
  - `float`, `Decimal` and `/` (true division) must not appear in `engine/cost.py`, `engine/budget.py` or the money code in `web/src/lib/format.ts`.
  - A schema test forbids real, double and numeric columns.
- INV-2: Every finding has a valid http(s) URL.
  - `services.findings.save_finding()` is the only insert path.
  - It validates through `schemas.FindingIn`: a non-empty title, an http(s) scheme, a non-empty host and at most 2048 chars.
  - It requires the normalized URL to have come from a `web_search` result in the same run.
  - The DB enforces NOT NULL plus a CHECK. Unsourced claims stay in assistant prose only.
- INV-3: Dedupe is race-safe and alerts are never empty.
  - Findings are inserted with `ON CONFLICT DO NOTHING` against the hash unique constraints, never check-then-insert.
  - `new_findings` counts only inserted rows.
  - When `new_findings == 0`, a watch run adds no message and makes no Notifier call.
- INV-4: Auth covers every route except `PUBLIC_PATHS = {"/health", "/api/auth/login"}`, which is defined once in `auth/deps.py`.
  - Every `/api/*` route outside `/api/v1/*` and `PUBLIC_PATHS` depends on `require_owner` (session only).
  - Every `/api/v1/*` route depends on `require_api_key` (Bearer only).
  - `/docs` and `/openapi.json` use `require_owner_or_key`. FastAPI's default docs, redoc and oauth2-redirect stay disabled.
  - Auth dependencies are attached at router level, so they run before validation and 401 comes before 404 or 422.
  - The route-coverage test (M3-C6) must keep passing, and any change to `PUBLIC_PATHS` must be called out in the PR.
- INV-5: API keys are `rb_` plus `secrets.token_urlsafe(32)`.
  - Only the sha256 hex is stored, looked up by hash and compared with `hmac.compare_digest`.
  - The plaintext appears only in the create response or the CLI output.
  - No list or detail response includes the key or its hash.
- INV-6: Secrets are never logged.
  - Covered secrets: API keys, the password and its hash, session cookies, the Telegram token, the Anthropic and Tavily keys, and the DB password.
  - They never reach logs, error bodies returned to clients, or URLs that get logged.
  - `SecretRedactingFilter` stays installed, and the `httpx`, `httpcore` and `telegram` loggers stay at WARNING or above.
- INV-7: Config comes only from env through `Settings` in `app/config.py`.
  - No `os.environ` or `os.getenv` elsewhere, and no secret literals in code.
  - `.env*` is gitignored except `.env.example`.
  - The keys in `.env.example` must equal the `Settings` fields plus `NON_SETTINGS_ENV` (test-enforced).
- INV-8: Tests never call real third-party APIs.
  - Anthropic, Tavily and Telegram are reached only through the protocols in `app/integrations/`.
  - Tests use `integrations/fakes.py` or respx-mocked HTTP, and pytest-socket blocks non-localhost hosts.
  - Frontend tests use the mock `ApiClient` or the full stack with `INTEGRATIONS_MODE=fake`.
  - Fake mode refuses to start when `APP_ENV=production`.
- INV-9: All LLM and search calls go through `RunBudget`, for every trigger (`chat|watch|telegram|api|digest`). Enforced from M10.
  - Before each LLM call, `spent + compute(prompt_bytes, LLM_MAX_TOKENS)` must be at most `RUN_BUDGET_CENTS`.
  - Before each search call, `spent + one search's price` must be at most `RUN_BUDGET_CENTS`, and `search_calls` must be below `RUN_MAX_SEARCH_CALLS`.
  - LLM calls are limited to `RUN_MAX_LLM_CALLS`, and every request sends `max_tokens=LLM_MAX_TOKENS`.
  - Once a cap is hit, no further LLM or search call is made in that run. The run ends `capped`, keeps its saved findings and is never retried.
  - `run.cost_cents` never exceeds `RUN_BUDGET_CENTS`, and `run.status` takes only `running|ok|capped|error`.
- INV-10: Runs are created only by `services.runs.open_run()`, using an INSERT that relies on DB uniqueness.
  - Scheduled claims use `INSERT … ON CONFLICT DO NOTHING RETURNING id`, which covers (research_id, scheduled_for) and `run_one_running_per_research`.
  - Interactive runs turn the unique violation into `Conflict` (409).
  - There is no select-then-insert and no in-memory "already ran" state.
  - The stale sweep marks `running` runs older than `RUN_STALE_AFTER_SECONDS` as `error`.
  - Enabling a watch or changing its schedule sets `watch_enabled_at`, so the first watch run happens in the next slot.
- INV-11: A run is never tied to an HTTP connection.
  - Interactive runs execute as tasks started by `start_background`, and SSE handlers only read from the sink.
  - A client disconnect must not cancel the task, lose the assistant message or leave the run `running`.
  - Every run ends in `ok|capped|error` with `finished_at` set, unless the process dies, in which case the stale sweep marks it `error`.
- INV-12: Telegram callback data is built only by `bot/callbacks.encode()`.
  - The format is `<action>:<int ids>[:<preset>]`, at most 64 bytes, with no titles, URLs or text.
  - Every bot handler, for messages and callbacks, checks `chat.id == OWNER_CHAT_ID` before any DB access or reply.
- INV-13: Schema changes go only through new Alembic migrations, and merged migrations are never edited. `alembic check` must pass (models match migrations).
- INV-14: The frontend is TypeScript strict with no `any` and no `@ts-ignore`.
  - Components never call `fetch` directly. All data goes through `ApiClient`, and `mock.ts` and `http.ts` implement the same interface.
  - Post-login redirects use `safeNext()`, which only allows paths that start with `/` and not `//` or `/\`.
- INV-15: The UI is mobile-first.
  - On every screen at 390×844, there is no horizontal scroll and every interactive element is at least 44px tall (Playwright mobile assertions).
  - Dark is the default theme, and there are no marketing pages.
- INV-16: The session cookie is `HttpOnly`, `SameSite=Lax` (so Telegram deep links keep the session) and `Secure` when `PUBLIC_BASE_URL` is https.
  - Login is rate-limited to `LOGIN_RATE_LIMIT_PER_MIN` attempts per 60 s per client IP, as derived only by `auth/client_ip.py`, and the limit returns 429.
- INV-17: Compose layout and startup order.
  - In `compose.yaml`, only `web` publishes a port, bound to `${BIND_ADDR}`.
  - `bot` and `web` depend on `api: service_healthy`, so nothing touches the DB before migrations run.
  - Dev and test port mappings live only in `compose.dev.yaml` and `compose.smoke.yaml`, which are used explicitly with `-f`.

## Conventions
- **Python:**
  - Use type hints everywhere and keep `mypy --strict` clean. Ruff handles lint and format (line length 100).
  - Modules are `snake_case`. Pydantic models are suffixed `In`/`Out` (`ResearchIn`, `FindingOut`).
  - Routers stay thin. They parse input, call one service function, and return an `Out` model.
- **Errors:**
  - Services raise domain exceptions (`NotFound`, `Conflict`, `ValidationFailed`). A single exception handler in `main.py` maps them to `{"detail": "..."}` with 404, 409 or 422.
  - Cap hits are a `RunBudget` result, not an HTTP error.
  - Never return stack traces or secrets.
  - Agent tool errors go back to the model as `is_error` tool results.
- **Time:** always UTC `timestamptz`. Get "now" from the injected `Clock`, never from `datetime.now()` inside services, the engine, the worker or auth.
- **Async tasks:**
  - Background runs are created only in `services.runs.start_background`, and their references are kept until done.
  - Tests await completion through a `wait_for_run(run_id)` helper and never sleep.
- **Backend tests:**
  - Tests run against real Postgres (`TEST_DATABASE_URL`). Migrations run once per session, and tables are truncated between tests.
  - Name tests `test_<behaviour>` and mark them with the criterion ID (`@pytest.mark.criterion("M8-C7")`).
  - Use FakeLLM (scripted text chunks, tool calls and token usage, plus recorded requests and an optional block-until-released chunk), FakeSearch (fixed results and a call counter), FakeNotifier and FakeTelegram (outbox).
  - Hypothesis covers cost, the budget bound, normalization and callback encoding.
- **Frontend:**
  - Components are `PascalCase.tsx` and hooks are `useX.ts`. Use Server Components by default and add `"use client"` only for interactive parts.
  - Tailwind only, no CSS-in-JS. Mobile layouts use `100dvh`, and the composer is pinned to the bottom with safe-area insets.
  - Vitest covers units such as `formatCents`, `safeNext`, the SSE parser, active-run polling and the Next config.
  - Playwright covers screens on the `desktop` and `mobile` projects (mock mode) and full-stack flows on the `stack` project. Screenshots go to `web/screenshots/<screen>-<project>.png`.
- **Git:** one milestone per PR, titled `M<n>: <title>`. Done-criterion IDs go in the PR body, each with the test and the `make` target that proves it.
