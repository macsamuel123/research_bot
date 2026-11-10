# PLAN

Research Bot is a single-owner personal research assistant. The owner gives it a topic. A Claude agent searches the web with Tavily and saves cited, deduplicated findings into a ChatGPT-style thread at `/r/<id>`, where the owner can keep chatting. An optional recurring watch (every 6h, daily or weekly) re-runs the research on a schedule. Each run is capped by a cost budget and a search-call limit, and only NEW findings are sent to the owner's Telegram chat as an alert that deep-links back to the thread. The same capability is exposed through an API-key-protected `/api/v1` for other bots (first: the LinkedIn social bot), including a ranked-themes digest. The phone is the primary device. The web UI is mobile-first and dark by default, sits behind a password login, and is reachable only over Tailscale. A run is never tied to the browser connection: if the phone drops the stream, the run finishes and the thread shows the result. Requirement IDs (R1–R26) used below are defined in the "Requirements traceability" section at the end of this file. The column-level schema is in CLAUDE.md "Schema". Every full-stack criterion is proven by `make e2e-stack`, which `make test` runs (see CLAUDE.md "Commands"). The orchestrator builds milestones top to bottom.

<!--
Format rules (the orchestrator parses this):
- Each milestone is a level-2 heading:  ## M<number>: <title>
- Optional line right under it:  ui: true | false
    ui: true  → coder builds a clickable UI on mock data first, you approve it from a
                preview link, then the backend gets built behind it.
    ui: false → backend/infra only. If omitted, defaults to true for repos with a UI framework.
- Done criteria are checkboxes with IDs:  - [ ] M1-C1: <testable statement>
  Every criterion must be provable by an automated test (or a screenshot for visual ones).
- Already-done milestones: tick all their boxes [x] and the orchestrator skips them.
-->

## M1: Monorepo scaffold, config, health and test fakes
ui: false
This milestone sets up:
- `api/`: FastAPI, Python 3.12, uv, SQLAlchemy 2, Alembic (no revisions yet) and psycopg3.
- `web/`: Next.js App Router, TypeScript strict and Tailwind, dark by default.
- The root `Makefile`, including the `e2e-stack` target that `make test` runs.
- `compose.yaml` (production-safe) and `compose.dev.yaml` (dev/test DB port).
- Env-based `Settings`, log redaction, and the integration protocols with their fakes.
- `/health` (R2).

Out of scope: tables (M2), auth (M3), screens (a placeholder root page is enough) and agent logic.
- [ ] M1-C1: On a fresh clone with `make db-up` running, `make install`, `make lint`, `make typecheck`, `make test` and `make build` each exit 0. A test asserts that `make -n test` invokes `test-api`, `test-web` and `e2e-stack`.
- [ ] M1-C2: `GET /health` returns 200 `{"status":"ok","db":"ok"}` when Postgres is reachable. It returns 503 `{"status":"degraded","db":"error"}` when the DB check raises (tested via a dependency override).
- [ ] M1-C3: `Settings` (pydantic-settings) fails at startup with an error naming the variable for each missing required var listed in CLAUDE.md "Settings" (parametrized test).
  - `RUN_BUDGET_CENTS`, `RUN_MAX_SEARCH_CALLS`, `RUN_MAX_LLM_CALLS`, `LLM_MAX_TOKENS`, `RUN_TIMEOUT_SECONDS` and the `PRICE_*` settings reject `0`, `-1`, `0.5` and `abc`, each with an error naming the variable.
  - Startup also fails when `RUN_STALE_AFTER_SECONDS <= RUN_TIMEOUT_SECONDS`, when `DIGEST_SYNTH_RESERVE_CENTS >= RUN_BUDGET_CENTS`, or when `INTEGRATIONS_MODE=fake` and `APP_ENV=production`.
  - It fails when `PUBLIC_BASE_URL` is not an absolute http(s) URL with a host, and when `APP_ENV=production` and `PUBLIC_BASE_URL` is not `https://`.
- [ ] M1-C4: A test asserts that the set of keys in `.env.example` equals the `Settings` field names plus exactly the `NON_SETTINGS_ENV` allowlist defined in `app/config.py` (`BIND_ADDR`, `API_INTERNAL_URL`, `NEXT_PUBLIC_USE_MOCKS`, `TEST_DATABASE_URL`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`). Every `.env.example` value is a placeholder, except `ANTHROPIC_MODEL` (marked with a "verify before deploy" comment) and non-secret defaults. `.env.example` contains comments recommending a Tailscale MagicDNS HTTPS hostname (via `tailscale serve`) for `PUBLIC_BASE_URL` and requiring `$$` escaping of `$` in `OWNER_PASSWORD_HASH` (a test greps for both).
- [ ] M1-C5: `git check-ignore` reports `.env` and `.env.local` as ignored and `.env.example` as not ignored (test).
- [ ] M1-C6: `SecretRedactingFilter` replaces any occurrence of a secret setting's value with `***`: `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `TELEGRAM_BOT_TOKEN`, `OWNER_PASSWORD_HASH`, `SESSION_SECRET`, and the DB password in `DATABASE_URL`. A caplog test proves it for messages, args and exception text. The `httpx`, `httpcore` and `telegram` loggers are set to WARNING or above.
- [ ] M1-C7: The integration seams exist and tests cannot reach the network:
  - pytest-socket blocks non-localhost network: a test that opens a connection to `api.anthropic.com` gets `SocketBlockedError`.
  - The `LLMClient`, `SearchClient` and `Notifier` protocols exist in `app/integrations/`, and `FakeLLM`, `FakeSearch` and `FakeNotifier` implement them (checked by mypy).
  - `INTEGRATIONS_MODE=fake` makes `get_integrations()` return the fakes (test).
- [ ] M1-C8: The frontend test runners work:
  - `pnpm test` (Vitest) and `pnpm test:e2e` (Playwright, with projects `desktop` 1280×800 and `mobile` 390×844, mock mode) each run at least one passing test. The root page renders with `<html class="dark">`.
  - `make e2e-stack` starts the api (`INTEGRATIONS_MODE=fake`, `APP_ENV=test`, test DB) and the web dev server, waits for `/health`, runs the Playwright `stack` project (at least one passing test that loads the root page), and stops both processes even when the tests fail.
- [ ] M1-C9: The compose files are valid and safe:
  - `docker compose -f compose.yaml config` validates and defines `postgres`, `api` and `web`, and postgres publishes no ports in it.
  - `docker compose -f compose.yaml -f compose.dev.yaml config` publishes postgres only on `127.0.0.1:5433`.
  - No `compose.override.yaml` is tracked in git (test).
  - The api container command runs `alembic upgrade head` before uvicorn.

## M2: Database schema and migrations
ui: false
This milestone adds the first Alembic migration with the MVP schema listed in CLAUDE.md "Schema" (R4), and the pytest DB fixtures (migrate once per session, truncate between tests). Out of scope: the items marked "M14 migration only" in that section (`research.topic_key` and `digest_cache`).
- [ ] M2-C1: `alembic upgrade head` on an empty DB creates `research`, `message`, `finding`, `run` and `api_key`. An inspection test compares every column, type, nullability, default and index against CLAUDE.md "Schema", column by column, excluding only the items marked "M14 migration only". `alembic downgrade base` followed by `upgrade head` succeeds, and `alembic check` reports no model/migration drift.
- [ ] M2-C2: `finding.url` is NOT NULL and has a CHECK `url ~ '^https?://'`. Inserting a finding with a NULL url, or with url `ftp://x.org`, raises IntegrityError (test).
- [ ] M2-C3: These unique constraints exist and reject duplicates (one test each):
  - finding `(research_id, dedupe_hash)`, `(research_id, url_hash)` and `(research_id, content_hash)`
  - run `(research_id, scheduled_for)`
  - the partial unique index `run_one_running_per_research` on run `(research_id) WHERE status = 'running'`. A second `running` run for one research is rejected, while a second run after the first is `ok` is accepted.
  - `api_key.key_hash`
- [ ] M2-C4: A schema-inspection test asserts that no column in the database has type real, double precision or numeric, and that `run.cost_cents` is `integer NOT NULL DEFAULT 0`.
- [ ] M2-C5: CHECK constraints limit `run.status` to `running|ok|capped|error`, `run.trigger` to `chat|watch|telegram|api|digest`, `message.role` to `user|assistant`, and `research.schedule` to NULL or `6h|daily|weekly`. Each rejection is tested.
- [ ] M2-C6: Deleting a research cascades to its messages, findings and runs (row counts are 0 afterwards). Deleting a run sets `finding.run_id` to NULL.

## M3: Owner login, session, proxy and route protection
ui: true
This milestone adds:
- the login screen (on mock data first), then real password auth and the session cookie
- client-IP-aware login rate limiting
- the Next.js `/api` proxy and the auth gate with deep-link return
- auth-protected docs routes
- the route-coverage 401 test that every later milestone inherits (R1)

It ships a placeholder `/r/[id]` page under the auth gate, which M5 replaces.
- [ ] M3-C1: `POST /api/auth/login` with the correct password (argon2-verified against `OWNER_PASSWORD_HASH`) returns 204 and sets cookie `rb_session` with `HttpOnly`, `SameSite=Lax` and `Path=/`, plus `Secure` when `PUBLIC_BASE_URL` starts with `https://`. A wrong password returns 401 and sets no cookie.
- [ ] M3-C2: `GET /api/auth/me` returns 200 with a valid session. It returns 401 with no cookie, a tampered cookie, or a cookie older than `SESSION_MAX_AGE_DAYS` (injected clock). `POST /api/auth/logout` clears the cookie.
- [ ] M3-C3: `auth.client_ip(request)` returns the TCP peer address unless the peer is inside `TRUSTED_PROXY_CIDRS`. In that case it returns the rightmost `X-Forwarded-For` entry. Unit tests:
  - (a) an `X-Forwarded-For` header from a non-trusted peer is ignored
  - (b) a trusted peer with `X-Forwarded-For: 6.6.6.6, 10.0.0.5` yields `10.0.0.5`
  - (c) a trusted peer with no header yields the peer address
- [ ] M3-C4: The 6th login attempt from one client IP (as derived by `client_ip`) within 60 s returns 429, even with the correct password. Two different forwarded IPs from the trusted proxy are bucketed separately. A spoofed `X-Forwarded-For` from a non-trusted peer does not escape that peer's bucket. Once the window passes (injected clock), login works again.
- [ ] M3-C5: FastAPI's default docs are disabled (`docs_url`, `redoc_url` and `openapi_url` are None). The app-defined `/docs` and `/openapi.json` require an owner session (401 without one, 200 with one). `/redoc` and `/docs/oauth2-redirect` are not registered.
- [ ] M3-C6: A route-coverage test iterates every (method, path) registered on the app. It fills path params with `1`, sends no body and no credentials, and expects 401 for every route not in the single `PUBLIC_PATHS` constant (`/health`, `/api/auth/login`). This proves auth runs before 404 and 422 validation.
- [ ] M3-C7: `python -m app.cli hash-password` reads the password without echo and prints an argon2 hash that `/api/auth/login` accepts (the test feeds stdin). `hash-password --compose` prints the same hash with every `$` doubled to `$$` (test).
- [ ] M3-C8: `next.config` rewrites `/api/:path*`, `/docs` and `/openapi.json` to `API_INTERNAL_URL`. It sets `compress: false` and sets `experimental.proxyTimeout` to at least `(RUN_TIMEOUT_SECONDS + 30) * 1000` (Vitest reads the config). Full-stack Playwright (`make e2e-stack`): an unauthenticated visit to `/r/42` redirects to `/login?next=%2Fr%2F42`, and after a successful login the browser lands on the placeholder `/r/42`.
- [ ] M3-C9: `safeNext()` only accepts paths that start with `/` and not `//` or `/\`. It returns `/` for `//evil.com`, `https://evil.com` and `/\evil.com` (Vitest).
- [ ] M3-C10: The login screen has a password input and a submit button, each at least 44px tall. It shows "Wrong password" on 401 and "Too many attempts, try again in a minute" on 429. At 390×844 there is no horizontal scroll (Playwright asserts `scrollWidth <= innerWidth`), and a mobile screenshot is saved.
- [ ] M3-C11: A caplog test runs a successful and a failed login and asserts that no log record contains the submitted password, the password hash or the cookie value.

## M4: API keys
ui: true
This milestone adds the API keys page (create, show once, revoke), which is one of the screens the BRD lists. It also adds the CLI equivalents and Bearer auth for `/api/v1/*` (R3). A stub `GET /api/v1/whoami` proves key auth until M13 adds the real v1 routes.
- [ ] M4-C1: `POST /api/keys` `{name}` (owner session) returns 201 `{id, name, key, created_at}`.
  - `key` is `rb_` followed by the output of `secrets.token_urlsafe(32)`, which is at least 43 url-safe chars.
  - The stored row holds only the sha256 hex in `key_hash`, and a test asserts the plaintext appears in no column.
  - A blank name or one over 100 chars returns 422.
- [ ] M4-C2: `GET /api/keys` returns `id, name, created_at, revoked_at` for each key and never a `key` or `key_hash` field.
- [ ] M4-C3: `POST /api/keys/{id}/revoke` sets `revoked_at`. After that, `GET /api/v1/whoami` with that key returns 401, while an active key gets 200 `{"name": ...}`.
- [ ] M4-C4: Owner credentials and key credentials are not interchangeable:
  - On `/api/v1/*`, a missing header, a non-Bearer scheme, an unknown key or a revoked key each return 401 with `WWW-Authenticate: Bearer`.
  - A valid API key on owner routes (`/api/keys`, `/api/auth/me`) returns 401, and so does an owner session cookie on `/api/v1/whoami`.
  - The M3-C6 route-coverage test covers the new routes.
- [ ] M4-C5: `python -m app.cli create-key <name>` prints the plaintext key once, `list-keys` prints no key material, and `revoke-key <id>` revokes the key (tests run them via subprocess against the test DB).
- [ ] M4-C6: The keys page has a create form and a show-once dialog with a copy button and a "you won't see this again" warning. After the dialog closes and the page reloads, only the name is shown. Revoke asks for confirmation and then shows the key as revoked. Playwright passes on desktop and mobile, and a mobile screenshot is saved.
- [ ] M4-C7: A caplog test creates a key and authenticates with it, and asserts that neither the plaintext key nor its hash appears in any log record.

## M5: App shell UI on mock data: landing, sidebar and thread
ui: true
This milestone defines the `ApiClient` interface for researches and messages, and implements it in `mock.ts` (deterministic fixtures plus simulated streaming). It builds these screens, running on the mock client only:
- the landing page (R5)
- the sidebar and drawer (R6)
- the thread message list and composer (R7 UI)
- unread clearing (R10 UI)
- the `/preview` phone frame

The backend endpoints and the `http.ts` wiring come in M6.
- [ ] M5-C1: `web/src/lib/api/client.ts` exports an `ApiClient` interface covering list, create, get, read, send-message and stream-response for researches, and `mock.ts` implements it (`tsc` passes). A Vitest test shows that the mock returns the same fixtures on every run.
- [ ] M5-C2: `sse.ts` parses `token`, `finding`, `done` and `error` events, including events split across chunk boundaries and multi-line `data:` fields (Vitest).
- [ ] M5-C3: The landing page shows the heading "What do you want to research?" and an input. The submit button is disabled while the input is blank. Submitting navigates to `/r/<new id>`, and the new research appears at the top of the sidebar (Playwright, mock mode).
- [ ] M5-C4: Each sidebar item shows the title, a relative last-activity time, an unread dot (`aria-label="unread"`) only when unread, and a watch indicator (`aria-label="watch on"` or `"watch off"`). A "New research" button at the top navigates to `/`. Items are ordered by `last_activity_at` desc.
- [ ] M5-C5: On mobile (390×844) the sidebar is a slide-over drawer, opened by a menu button and closed on navigation or a backdrop tap. On desktop it is always visible. On mobile, no screen scrolls horizontally (`scrollWidth <= innerWidth`).
- [ ] M5-C6: The thread page tells user and assistant messages apart (`data-role`). The composer stays inside the viewport after the message list scrolls (bounding-box check on mobile). Playwright sees partial assistant text before the final text.
- [ ] M5-C7: Opening a thread whose sidebar item shows the unread dot removes the dot (Playwright, mock mode).
- [ ] M5-C8: A Playwright check asserts that every visible `button`, `a` and `input` on Login, Landing, Thread and the open drawer is at least 44px tall at the mobile viewport.
- [ ] M5-C9: `/preview` renders the app inside a 390×844 phone frame when `NEXT_PUBLIC_USE_MOCKS=1` and returns 404 otherwise. Playwright saves mobile screenshots of Login, Landing, Thread and the open drawer to `web/screenshots/`.

## M6: Research CRUD API and shell wiring
ui: false
This milestone adds the owner research endpoints and `http.ts`, and runs the M5 screens against the real backend (R5, R6, R10). Messages are stored without an agent reply until M9 wires the engine to the endpoints.
- [ ] M6-C1: `POST /api/researches` `{topic}` returns 201 `{id}`. It sets `title` to the trimmed topic cut to 80 chars, stores the topic as the first `user` message, and sets `last_activity_at = now`. A blank topic or one over 2000 chars returns 422.
- [ ] M6-C2: `GET /api/researches` returns `id, title, last_activity_at, unread, watch_enabled, schedule`, sorted by `last_activity_at` desc. With 200 researches it runs at most 2 SQL queries (SQLAlchemy event counter test).
- [ ] M6-C3: `GET /api/researches/{id}` returns the research plus its messages in creation order. An unknown id returns 404. `POST /api/researches/{id}/messages` stores a user message (non-streaming until M9) and bumps `last_activity_at`.
- [ ] M6-C4: `POST /api/researches/{id}/read` sets `unread=false`, and an unknown id returns 404 (test).
- [ ] M6-C5: `http.ts` implements `ApiClient` (`tsc` passes), and no component calls `fetch` directly (a lint rule or grep test).
- [ ] M6-C6: Full-stack Playwright (`make e2e-stack`) covers the shell:
  - Log in, submit a topic on the landing page, land on `/r/<id>` with the topic shown as a user message, and see the research at the top of the sidebar.
  - A seeded unread research loses its dot when opened, and the dot stays cleared after a reload.

## M7: Findings panel, watch settings and run history
ui: true
This milestone builds the Findings panel with dismiss (R8), the watch settings (R9) and the run history list (R18 display), on mock data first and then wired to real endpoints. Runs only exist once M8 lands, so the wired tests seed run rows directly.
- [ ] M7-C1: `GET /api/researches/{id}/findings` returns non-dismissed findings (`id, title, url, summary, source, found_at`), sorted by `found_at` desc. `POST /api/findings/{id}/dismiss` returns 204, is idempotent, and makes the finding disappear from the list. An unknown id returns 404.
- [ ] M7-C2: `PATCH /api/researches/{id}` `{watch_enabled?, schedule?}` returns 422 for any schedule outside `6h|daily|weekly`. Enabling a watch with no schedule sets `daily`. Enabling a watch or changing its schedule sets `watch_enabled_at = now`. Pausing (`watch_enabled=false`) keeps the schedule.
- [ ] M7-C3: `DELETE /api/researches/{id}` returns 204 and removes the research with its messages, findings and runs. A later GET returns 404.
- [ ] M7-C4: `GET /api/researches/{id}/runs` returns `id, started_at, finished_at, status, trigger, cost_cents (int), new_findings`, newest first.
- [ ] M7-C5: Each finding in the Findings panel shows its title, its summary and a source link with `target="_blank" rel="noopener noreferrer"`. Dismiss removes the item. On mobile, Findings, Watch and Runs sit in a bottom sheet or tabs. On desktop they sit in a side panel.
- [ ] M7-C6: The watch settings have an on/off toggle, preset buttons (every 6h, daily, weekly) and pause, and the sidebar watch indicator updates right away. Delete opens a confirm dialog. Cancel keeps the research. Confirm deletes it, navigates to `/` and removes it from the sidebar (Playwright in mock mode, and full stack via `make e2e-stack`).
- [ ] M7-C7: Run history shows the time, a status badge (`running|ok|capped|error`), the cost and the new-findings count. The cost comes from `formatCents()`, which uses only integer math (Vitest: 0→"$0.00", 5→"$0.05", 1234→"$12.34").
- [ ] M7-C8: Mobile screenshots of the Findings, Watch settings and Run history views are saved to `web/screenshots/`, with no horizontal scroll and every touch target at least 44px.

## M8: Research engine core: agent loop, tools, dedupe and cost
ui: false
This milestone adds the engine, tested directly through services and fakes without HTTP streaming (R11, R12, R13):
- `services.runs.open_run()`, which atomically inserts the run row and the user message
- `services.runs.execute()`, which calls `engine.agent.run_turn` and finalizes the run
- the Claude agent loop with the `web_search` and `save_finding` tools
- the Anthropic and Tavily clients
- finding validation, URL normalization and dedupe
- integer-cent cost

All LLM and search calls go through a `RunBudget` object that tracks usage. M10 adds cap enforcement inside it. Out of scope: SSE, background tasks and UI wiring (M9).
- [ ] M8-C1: `open_run(research_id, trigger, user_content=None, scheduled_for=None)` inserts the `running` run row and, when given, the user message, in one transaction, and returns the run id.
  - It raises `Conflict` when the research already has a `running` run. In that case no user message and no run row are stored.
  - Two concurrent `open_run` calls for one research on separate connections give exactly one success and one `Conflict`.
- [ ] M8-C2: `execute(run_id, sink)` sends `token`, `finding` and `done` (`{run_id, status, cost_cents, new_findings}`) events to the sink, in order. The user message is already committed when FakeLLM is first called (FakeLLM checks the DB). The full assistant message is persisted before `done` is emitted.
- [ ] M8-C3: If the LLM raises, the sink gets an `error` event, the run is marked `error` with `finished_at` set, the user message remains, and any partial assistant text is persisted followed by "(stopped: error)".
- [ ] M8-C4: On follow-up turns, the prior messages of the thread and the URLs of already-stored findings are sent to the LLM (checked on FakeLLM's recorded requests).
- [ ] M8-C5: `save_finding` returns an error tool result to the model, and inserts no row, when the url:
  - is missing or empty
  - is not http(s)
  - has no host
  - does not match, after normalization, a URL that `web_search` returned in this run

  Valid input is inserted with `source` set to the hostname and `run_id` set.
- [ ] M8-C6: URL normalization (table-driven unit tests plus a Hypothesis idempotence property):
  - `HTTPS://WWW.Example.COM/a?utm_source=x&b=2&a=1#top` becomes `https://www.example.com/a?a=1&b=2`.
  - It lowercases the scheme and host and strips the fragment.
  - It strips `utm_*`, `fbclid`, `gclid`, `mc_cid`, `mc_eid` and `ref`, and sorts the remaining params.
- [ ] M8-C7: Dedupe works as follows:
  - The same normalized URL with a different title is skipped.
  - A different URL with the same normalized title and summary is skipped.
  - Two concurrent inserts of one finding on separate connections produce exactly one row (`ON CONFLICT DO NOTHING`).
  - `new_findings` counts only inserted rows.
- [ ] M8-C8: Each executed chat run ends `status=ok` with `input_tokens`, `output_tokens`, `search_calls` and `cost_cents` from `engine.cost.compute()`, and with `finished_at` set. It updates `research.last_run_at` and `last_activity_at` and leaves `unread` unchanged.
- [ ] M8-C9: `cost.compute()` takes and returns only ints and does a single ceiling division to whole cents. Hypothesis property tests check that the result is an int, is at least 0, and never decreases as tokens or searches increase.
- [ ] M8-C10: The real clients are tested through respx-mocked HTTP:
  - `AnthropicLLM` uses the model from the required `ANTHROPIC_MODEL` setting and sends `max_tokens=LLM_MAX_TOKENS`. A test checks that the model ID from settings appears in the request body.
  - `TavilySearch` sends the configured key.

## M9: Streaming, run lifecycle and thread wiring
ui: true
This milestone exposes the engine over SSE through the Next proxy and wires the composer and the first turn after landing to the real stream (R7, R11). Runs are decoupled from the HTTP request. `services.runs.start_background(research_id, trigger, user_content=None, sink=None)` runs `open_run` and then `execute` as an asyncio task in the calling process. The SSE response only subscribes to the task's sink. A client disconnect never cancels a run. A thread opened while a run is `running` shows a "Researching…" state and polls until the run finishes. A second send while a run is active returns 409. The UI states are built on mock data first, then wired.
- [ ] M9-C1: `POST /api/researches/{id}/messages` `{content}` and `POST /api/researches/{id}/respond` stream the run's events:
  - `/respond` answers the pending last user message.
  - Both return `text/event-stream` with `Cache-Control: no-cache` and `X-Accel-Buffering: no`, and emit `token`, `finding`, `done` and `error` events.
  - No GZip middleware is installed.
- [ ] M9-C2: Responses are not buffered by the backend. With a FakeLLM that blocks after its first chunk until the test releases it, the test client receives the first `token` event before the release.
- [ ] M9-C3: Client disconnect: a test drives the ASGI app directly and sends `http.disconnect` right after the first `token` event. The run task keeps going: FakeLLM's script is fully consumed, the complete assistant message and the findings are persisted, and the run ends `ok` with `finished_at` set. The server logs no unhandled exception.
- [ ] M9-C4: Conflicts and pending turns:
  - `messages` while the research has a `running` run (of any trigger) returns 409 `{"detail":"a run is already in progress"}` and stores no message.
  - `respond` returns 409 when a run is `running` or when the last message is not a `user` message. Neither case creates a run row.
  - `start_background` keeps a strong reference to each task until it finishes (a test checks that the task set is empty afterwards).
- [ ] M9-C5: `GET /api/researches/{id}` includes `active_run`, which is `{id, trigger, started_at}` while a run is `running` and `null` otherwise (test).
- [ ] M9-C6: UI, mock mode first:
  - When `active_run` is non-null, the thread shows a `role="status"` "Researching…" indicator, disables the composer's send button, and refetches the research every 2 s.
  - When `active_run` turns null, it stops polling and shows the new assistant message and findings.
  - A 409 on send shows "Still working on the previous answer", the draft text stays in the composer, and no message is added to the list.
  - Vitest with fake timers and Playwright mock mode cover this, and a mobile screenshot of the Researching state is saved.
- [ ] M9-C7: Full-stack Playwright (`make e2e-stack`, `INTEGRATIONS_MODE=fake`, `FAKE_LLM_CHUNK_DELAY_MS=300`), through the Next proxy:
  - After a topic is submitted on the landing page, partial assistant text is visible while the `done` event has not yet arrived (the final text is still absent). A finding then appears in the panel.
  - Reloading mid-run shows "Researching…" and starts no second run (the runs endpoint lists exactly one run). The final reply then appears without a manual reload.
- [ ] M9-C8: Full-stack Playwright (`make e2e-stack`): the page is closed mid-stream and the thread is opened in a new page. The final reply appears there, and the research has exactly one run, with status `ok`.

## M10: Run budget and call caps
ui: false
This milestone enforces `RUN_BUDGET_CENTS`, `RUN_MAX_SEARCH_CALLS`, `RUN_MAX_LLM_CALLS` and `RUN_TIMEOUT_SECONDS` inside `RunBudget` for every trigger (R16). Cost is projected before each call, so the budget can never be overshot. Capped runs are never retried by the engine. Retry-free scheduling is covered in M11.
- [ ] M10-C1: The budget is checked before every call:
  - Before each LLM call, `RunBudget` computes `projected = spent + cost.compute(input_tokens=len(prompt_bytes), output_tokens=LLM_MAX_TOKENS, searches=0)`. If `projected > RUN_BUDGET_CENTS`, the call is not made and the run ends `capped`.
  - Before each search call, `spent + one search's price` is checked the same way.
  - A test sets a budget that allows exactly one LLM call and checks that FakeLLM is called once and the run is `capped`.
- [ ] M10-C2: A Hypothesis property over random FakeLLM scripts (token usages and tool calls) shows that the final `run.cost_cents` never exceeds `RUN_BUDGET_CENTS`.
- [ ] M10-C3: The call caps hold:
  - With `RUN_MAX_SEARCH_CALLS=3` and a FakeLLM that asks for 5 searches, FakeSearch is called exactly 3 times, and the run ends `capped` with `search_calls=3`.
  - With `RUN_MAX_LLM_CALLS=4` and a FakeLLM that loops on tool calls forever, FakeLLM is called exactly 4 times, and the run ends `capped`.
- [ ] M10-C4: A capped run keeps the findings saved before the cap, and persists the partial assistant text followed by "(stopped: run budget reached)". It produces exactly one run row with no retry, and the SSE `done` event reports `status: "capped"`.
- [ ] M10-C5: A run that exceeds `RUN_TIMEOUT_SECONDS` (FakeLLM sleeps, short timeout in the test) ends `status=error` with `finished_at` set.
- [ ] M10-C6: The cap tests for C1 and C3 are parametrized over `trigger` in `chat|watch|telegram|api|digest` through `engine.agent.run_turn`, and pass for each.

## M11: Scheduled watches
ui: false
This milestone adds a DB-polling worker inside the api process (`WORKER_ENABLED`). It claims UTC slots, is restart-safe, and either alerts or does nothing (R14, R15, R17, and the data for R18). Runs are executed through `services.runs.start_background()` (M9). Alerts go through the `Notifier` protocol, and Telegram delivery arrives in M12.
- [ ] M11-C1: `slots.current_slot(ts, schedule)` floors UTC epoch time to 6h, 24h or 7d buckets (table tests, including boundaries).
- [ ] M11-C2: Background runs finish by trigger:
  - Background runs with trigger `api` or `telegram` persist the assistant message and findings on completion, set `unread=true`, and update `last_run_at` and `last_activity_at`.
  - `chat` runs leave `unread` unchanged.
  - An engine exception in any background run marks it `error` with `finished_at` set.
- [ ] M11-C3: A research is due when:
  - `watch_enabled=true`
  - `schedule` is set
  - `current_slot(now) > current_slot(watch_enabled_at)`
  - and no run exists for `(research_id, current_slot(now))`

  `worker.tick(now)` runs every due research with `trigger=watch` and `scheduled_for=slot`. Disabled watches and researches with no schedule never run.
- [ ] M11-C4: A watch enabled mid-slot does not run until the next slot. Test: the research is created and run at 10:00 UTC and daily is enabled at 10:01. A tick at 10:02 creates no run, and a tick at 00:00 the next day creates one.
- [ ] M11-C5: The run is claimed with `INSERT … ON CONFLICT DO NOTHING RETURNING id`, which covers both the `(research_id, scheduled_for)` unique constraint and `run_one_running_per_research`. In the test, two workers on separate DB connections tick concurrently with the same `now`, and the result is exactly one run row and one engine invocation.
- [ ] M11-C6: A watch that is due while a `chat` run is `running` on the same research creates no run and raises no error in that tick. It runs on the first tick after the chat run ends, within the same slot (test).
- [ ] M11-C7: Restart simulation: worker A claims a run and stops without finishing. Worker B then starts up, and its startup sweep marks `running` runs (of any trigger) older than `RUN_STALE_AFTER_SECONDS` as `error`, with `finished_at` set. B does not re-run that slot, and the next slot runs normally. The sweep also runs at the start of every tick.
- [ ] M11-C8: Watch runs alert only on new findings:
  - When a watch run has `new_findings == 0`, it adds no message, makes no Notifier call, and leaves `unread` and `last_activity_at` unchanged.
  - When `new_findings > 0`, it adds one assistant message that lists only the new findings, sets `unread=true`, updates `last_activity_at`, and calls the Notifier once with the run id.
- [ ] M11-C9: The watch prompt includes the topic, `last_run_at`, and the URLs of all stored findings (checked on FakeLLM's recorded request). Suppose FakeSearch returns 3 already-stored URLs and 2 new ones. The run then records `new_findings=2`, and the message and the Notifier payload contain only those 2.
- [ ] M11-C10: A watch run that ends `capped` or `error` is not retried by further ticks in the same slot. It runs again only in the next slot.
- [ ] M11-C11: An exception while running one watch marks that run `error` and does not stop the other due watches in the same tick. Watch runs appear in `GET /api/researches/{id}/runs`.

## M12: Telegram bot
ui: false
This milestone adds the Telegram side (R19–R22):
- **The `bot` compose service:** `python -m app.bot`, using python-telegram-bot long polling, for owner-only research creation and callbacks. Runs started from Telegram execute in the bot process via `start_background(trigger="telegram")`.
- **`TelegramNotifier`:** sends alerts. Watch alerts go out from the api process through the Bot API over HTTPS, with no polling.

The bot runs the stale-run sweep on startup.
- [ ] M12-C1: A text message from `OWNER_CHAT_ID` creates a research with a background run (`trigger=telegram`).
  - The bot replies with an [Open] URL button to `{PUBLIC_BASE_URL}/r/<id>` and the buttons [Watch 6h], [Watch daily] and [Watch weekly], encoded as `watch:<id>:<preset>`.
  - A watch button sets `watch_enabled=true`, `schedule` and `watch_enabled_at`, so the first watch run happens in the next slot (the M11-C4 rule; test).
- [ ] M12-C2: Messages and callbacks from any other chat ID cause no DB writes and no bot API calls (the test asserts unchanged row counts and an empty FakeTelegram outbox).
- [ ] M12-C3: `callbacks.encode/decode` supports only `pause:<research_id>`, `dismiss:<run_id>` and `watch:<research_id>:<preset>`. A Hypothesis test shows that the encoded value is at most 64 bytes for any IDs up to 2^63−1 and that decode inverts encode. Malformed or unknown data is ignored.
- [ ] M12-C4: After a `watch` or `telegram` run with new findings, an alert is sent. It shows the count and the top 3 titles as HTML-escaped links, plus an inline keyboard with [Open] (url), [Pause watch] (`pause:<research_id>`) and [Dismiss] (`dismiss:<run_id>`). No alert is sent when `new_findings == 0`, or for `chat`, `api` or `digest` runs.
- [ ] M12-C5: The pause callback sets `watch_enabled=false`. The dismiss callback sets `dismissed=true` only on findings with that `run_id`, and findings from other runs are unchanged. Both answer the callback query.
- [ ] M12-C6: A callback with valid data whose chat ID is not `OWNER_CHAT_ID` changes nothing (test).
- [ ] M12-C7: `TelegramNotifier` is tested with respx. A caplog test of an alert send shows that the bot token, which appears in Bot API URLs, is in no log record.
- [ ] M12-C8: `docker compose -f compose.yaml config` defines a `bot` service that uses the api image with command `python -m app.bot`, publishes no ports, and has `WORKER_ENABLED=false`.

## M13: Public API v1 and OpenAPI docs
ui: false
This milestone adds API-key-protected research creation and reads, the findings feed, and OpenAPI docs that accept either an owner session or an API key, with Bearer auth declared (R23, R24, R26). API-created runs execute in the api process via `start_background(trigger="api")`.
- [ ] M13-C1: `POST /api/v1/researches` `{topic, watch?: "6h"|"daily"|"weekly"}` returns 202 `{id, run_id}`. It stores the topic as the first user message and starts a background run with `trigger=api`. If `watch` is given, it sets `watch_enabled=true`, `schedule` and `watch_enabled_at`. An invalid topic or watch value returns 422.
- [ ] M13-C2: After the background run finishes (FakeLLM), the research shows in `GET /api/researches` with `unread=true` and has an assistant message, and its findings appear in `GET /api/researches/{id}/findings` (test).
- [ ] M13-C3: `GET /api/v1/researches` and `GET /api/v1/researches/{id}` return `id, title, topic, created_at, watch_enabled, schedule, last_run_at`. An unknown id returns 404.
- [ ] M13-C4: `GET /api/v1/researches/{id}/findings?since=<ISO8601>` returns exactly the keys `title, url, summary, found_at`. It excludes dismissed findings and those with `found_at < since`. A `since` that is not valid ISO8601 returns 422.
- [ ] M13-C5: `/openapi.json` declares an `HTTPBearer` security scheme, and every `/api/v1/*` operation references it (the test walks the schema).
- [ ] M13-C6: `/docs` and `/openapi.json` return 200 with an owner session or a valid API key, and 401 with neither or with a revoked key. The M3-C6 route-coverage test still passes and covers every new route.

## M14: Digest endpoint
ui: false
This milestone adds `GET /api/v1/digest?topic=&days=` (R25). It returns ranked themes built from stored findings plus one capped research run.
- It is synchronous and cached for `DIGEST_CACHE_HOURS` (24) per (topic key, days), which is the assumed answer to the BRD's open question on digests.
- A new migration adds `research.topic_key` (indexed) and `digest_cache`.
- Theme synthesis is one tool-less LLM call inside the same digest run, with a deterministic fallback, so it never breaks the run caps.
- [ ] M14-C1: `days` defaults to 7 and must be an integer from 1 to 90 (422 otherwise). `topic` is required and must not be blank (422). Without a valid API key the endpoint returns 401.
- [ ] M14-C2: `topic_key(topic)` applies NFKC normalization, lowercases, trims, and collapses internal whitespace to single spaces (table tests).
  - Every research gets `topic_key` on create, and the migration backfills existing rows.
  - The digest uses the most recent research with a matching `topic_key`, or creates one.
  - A research the digest creates shows in the owner sidebar with `unread=false`, and digest runs never call the Notifier.
- [ ] M14-C3: The digest makes exactly one run row (`trigger=digest`). Its research phase uses the agent loop with a budget of `RUN_BUDGET_CENTS − DIGEST_SYNTH_RESERVE_CENTS` and the normal search and LLM call caps. If the research phase hits a cap, the run status is `capped`.
- [ ] M14-C4: Synthesis makes one LLM call with no tools and `max_tokens=LLM_MAX_TOKENS`.
  - Its input is at most the 40 newest non-dismissed findings of that research with `found_at` in the last `days` days, with summaries cut to 300 chars.
  - It goes through the same `RunBudget` projection against the full `RUN_BUDGET_CENTS`, and its cost is added to the same run's `cost_cents`.
  - A test asserts that the final `cost_cents <= RUN_BUDGET_CENTS`.
- [ ] M14-C5: The response is `{topic, days, generated_at, partial, themes:[{rank, title, rationale, links:[url,…]}]}`, with ranks 1..n.
  - Each rationale is one line of at most 200 chars with no newline.
  - Each theme has at least 2 links, and every link equals the URL of a stored, non-dismissed finding.
  - Themes that fail validation are dropped, and at most 5 are returned.
- [ ] M14-C6: The deterministic fallback is used when the synthesis projection does not fit (no LLM call is made, so FakeLLM's call count is unchanged), when the synthesis call errors, or when fewer than 3 LLM themes pass validation.
  - It groups findings by `source` host, ranks groups by count and then by newest `found_at`, and keeps groups with at least 2 findings.
  - Each theme gets the title `<host>` and the rationale `<n> findings from <host> in the last <days> days`.
  - The response has `partial: true` whenever the fallback is used or fewer than 3 themes remain, and it is always 200.
- [ ] M14-C7: A second identical request (same `topic_key` and `days`) within `DIGEST_CACHE_HOURS` makes no LLM or search calls and returns the cached body. After 24h (injected clock), the digest is recomputed and the cache row is replaced.
- [ ] M14-C8: Two concurrent first requests for the same (`topic_key`, `days`) serialize on a Postgres advisory lock keyed on that pair. The result is exactly one research, one digest run and one cache row, and both responses return the same body. If a non-digest run is `running` on the matched research, the endpoint returns 409 and makes no LLM or search calls.

## M15: Deployment hardening
ui: false
This milestone finalizes the production `compose.yaml` (`api`, `web`, `postgres`, `bot`), with only the web service exposed on the Tailscale address. It covers:
- pinning the web proxy's address for `TRUSTED_PROXY_CIDRS`
- startup ordering, so the bot waits for migrations
- password-hash interpolation safety
- a secret scan
- a full-stack smoke test under compose with fake integrations

Once this milestone lands, `make test` also runs `make smoke`.
- [ ] M15-C1: A test parses `docker compose -f compose.yaml config` and asserts that `postgres`, `api` and `bot` publish no ports. `web` publishes only on `${BIND_ADDR}`, which is the Tailscale IP, or `127.0.0.1` when `tailscale serve` fronts it. No port mapping omits the host IP or uses `0.0.0.0`.
- [ ] M15-C2: Every service has `restart: unless-stopped`.
  - Postgres has a healthcheck, and `api` has a healthcheck on `/health`.
  - `api` depends on `postgres: service_healthy`.
  - `bot` depends on `api: service_healthy`, so it starts only after `alembic upgrade head` has run, and `web` depends on `api: service_healthy` (test parses the config).
- [ ] M15-C3: Compose defines an internal network with a fixed subnet and a static IP for `web`. The `api` service's `TRUSTED_PROXY_CIDRS` equals `<web ip>/32` (test parses the config).
- [ ] M15-C4: `make build` builds production images, and the web image runs a standalone `next start` build.
- [ ] M15-C5: A secret-scan test over `git ls-files` finds no match for any of these outside the `.env.example` placeholders: `sk-ant-`, `tvly-`, Telegram bot token patterns (`\d{8,10}:[A-Za-z0-9_-]{35}`), or `rb_` keys of 43 or more chars.
- [ ] M15-C6: The test writes a temp env file containing the output of `hash-password --compose` and runs `docker compose --env-file <tmp> -f compose.yaml config`. The resolved `OWNER_PASSWORD_HASH` of `api` equals the unescaped argon2 hash and verifies against the password.
- [ ] M15-C7: `make smoke` starts the stack with `compose.yaml` plus `compose.smoke.yaml` (`INTEGRATIONS_MODE=fake`, `APP_ENV=test`, `BIND_ADDR=127.0.0.1`) and runs a Playwright journey against the production build:
  - log in, create a research, see partial streamed text before `done`, and see a finding
  - close the page mid-run, reopen the thread, and see the final reply
  - open the keys page and create a key
  - check that a login attempt with a forged `X-Forwarded-For` counts against the real client's bucket

  It then tears the stack down, and the whole command exits 0.

## Requirements traceability
| ID | Requirement (from the BRD) | Milestones |
|---|---|---|
| R1 | Owner login with one argon2 password hash. It sets an httpOnly SameSite session cookie, everything except `/health` and login needs auth, and unauthenticated requests get 401. | M3 |
| R2 | `GET /health` returns 200 with DB status. | M1 |
| R3 | Owner-created, named API keys, shown once and stored hashed. Revoked keys get 401. Auth is `Authorization: Bearer`. | M4 |
| R4 | Postgres schema via Alembic: research, message, finding, run, api_key, plus `research.unread`, `research.last_activity_at` and the finding unique constraint on (research_id, dedupe_hash). | M2 |
| R5 | Landing page "What do you want to research?" whose submit creates a research and goes to `/r/<id>`. | M5, M6 |
| R6 | Sidebar with title, last activity, unread dot, watch indicator and a "New research" button, sorted by last activity. | M5, M6 |
| R7 | Thread page with owner and agent messages, SSE-streamed answers and a follow-up input. | M5, M9 |
| R8 | Findings panel with title, summary, a source link, and dismiss. | M7 |
| R9 | Watch settings: toggle, 6h/daily/weekly presets, pause, and delete with confirm. | M7 |
| R10 | The unread dot clears when the thread is opened. | M5, M6 |
| R11 | Claude agent loop with a Tavily search tool that streams tokens and persists the user and assistant messages. | M8, M9 |
| R12 | Every finding has a valid http(s) URL, and unsourced claims stay in prose only. | M2, M8 |
| R13 | `dedupe_hash` comes from the normalized URL plus a content hash, and a finding is skipped if either already exists. | M2, M8 |
| R14 | The scheduler runs due watches and writes run rows (status, cost_cents, new_findings). | M11 |
| R15 | Runs report only new findings, and zero new findings means no alert and no message. | M11 |
| R16 | Per-run caps `RUN_BUDGET_CENTS` and `RUN_MAX_SEARCH_CALLS` in integer cents. A capped run is `capped` and is not retried. | M1, M10 |
| R17 | Atomic run claiming with no double-fires, and stale `running` runs are marked `error` on startup. | M2, M8, M11 |
| R18 | Run history visible in the thread. | M7, M11 |
| R19 | Owner-only Telegram bot: text creates a research (plus an optional watch) and the reply has an [Open] link. | M12 |
| R20 | Alert with the count, the top 3 titles and their links, and the buttons [Open], [Pause watch] and [Dismiss]. | M12 |
| R21 | callback_data holds only an action and IDs, stays under 64 bytes, and is re-checked against the owner chat ID. | M12 |
| R22 | Dismiss marks the alert's findings dismissed, and Pause disables the watch. | M12 |
| R23 | `POST /api/v1/researches` plus `GET` list and detail. | M13 |
| R24 | `GET /api/v1/researches/{id}/findings?since=`, excluding dismissed findings. | M13 |
| R25 | `GET /api/v1/digest?topic=&days=` with 3–5 ranked themes, each with a rationale and 2+ links, subject to the caps, with days defaulting to 7. | M14 |
| R26 | OpenAPI docs at `/docs` with Bearer auth declared. | M3, M13 |
| NFR | Access tests, citations, dedupe, integer cents, hashed keys, no secret logging, `.env` hygiene, a restart-safe scheduler, the login rate limit, and Compose deployment over Tailscale only. | M1–M15 (see CLAUDE.md invariants) |

## Out of scope
Deferred from the BRD for the MVP:
- Multi-user or teams, billing, X/Twitter scraping, voice, email digests, a mobile app, social posting (the LinkedIn bot does that), and UI auth providers (no Clerk or Auth0).
- A global daily or monthly spend cap. Only the per-run caps are built.
- Custom cron schedules or intervals other than the presets. The minimum interval is 6h.
- Backfilling missed watch slots after downtime. Only the current slot runs.
- An async or queued `/digest`. It is synchronous, capped and cached for 24h.
- The Exa search provider. The `SearchClient` protocol leaves room for it later.
- API key scopes or expiry, and changing the password from the UI. To change it, run `app.cli hash-password` and update the env var.
- A Telegram "hide alert only" variant. [Dismiss] dismisses that alert's findings.
- Resuming a run interrupted by a process crash or restart. The stale sweep marks it `error`, and watches run again in the next slot.
- Re-attaching to a live token stream after a disconnect. The thread polls and shows the final reply instead.
- Cancelling a running run from the UI, and queueing a second message while a run is active. That send returns 409.

Assumed answers to the BRD open questions and other decisions (the owner may override them through env):
- Caps default to 50¢ and 8 searches per run. 12 LLM calls per run and `LLM_MAX_TOKENS=2048` bound the agent loop.
- Watch frequencies are 6h, daily and weekly. A newly enabled watch first runs at the next slot boundary.
- `/digest` is synchronous, capped and cached for 24h per (topic key, days). This caching goes beyond the BRD's explicit requirements and follows its stated assumption. Digest-created researches are visible in the sidebar but are never marked unread or alerted.
- Dismiss marks the alert's findings dismissed.
- API keys can be created from both the UI (the API keys page is one of the BRD's screens) and the CLI.
- One run at a time per research. A chat send during any active run returns 409, and a watch that comes due during a chat run waits for the next tick.
- `ANTHROPIC_MODEL` is required, with no code default. `.env.example` carries `claude-sonnet-5-5` as a placeholder. That is the Sonnet-class ID in Anthropic's published model list as of 2026-11, and the owner must confirm it against the current list before deploying. The `PRICE_*` defaults are also placeholders that must be checked against current Anthropic and Tavily pricing.
- `PUBLIC_BASE_URL` must be https in production. The recommended setup is a Tailscale MagicDNS hostname served via `tailscale serve`. A bare `http://100.x.y.z` URL may be rejected by Telegram as a button URL and would break the `Secure` cookie.
