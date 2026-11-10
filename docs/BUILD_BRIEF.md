## Product
Research Bot is a single-owner personal research assistant. The owner gives it a topic, and a Claude agent searches the web (Tavily) and saves cited findings in a ChatGPT-style thread. An optional recurring watch re-runs the research on a schedule and sends only NEW findings to Telegram. Each alert deep-links to `/r/<id>`, where the owner can keep chatting. The same capability is exposed through an API-key-protected `/api/v1` for other bots (first: the LinkedIn social bot).

## Users & roles
- **Owner (the only human):** logs into the web UI with a password, messages the Telegram bot from the owner chat ID, and creates, chats in, watches, pauses, dismisses and deletes researches.
- **API client (other bots):** holds a Bearer API key and can create researches and read researches, findings and digests. It cannot use the UI or manage keys.
- **Anyone else:** gets 401 everywhere. The Telegram bot silently ignores other chat IDs.

## MVP requirements
**Auth & keys (M1)**
- R1: Owner login with a single password (hash in env or DB, argon2/bcrypt). It issues an httpOnly, SameSite session cookie. All UI/API routes except `/health` and login require auth, and unauthenticated requests get 401.
- R2: `GET /health` returns 200 with DB connectivity status.
- R3: API keys are created by the owner (UI or CLI), have a name, and are shown once in plaintext. Only a hash is stored (`api_key(id, name, key_hash, created_at, revoked_at)`). Revoked keys get 401. Auth header: `Authorization: Bearer <key>`.
- R4: Postgres schema via migrations (Alembic) with these tables:
  - `research(id, title, topic, created_at, watch_enabled, schedule, last_run_at)`
  - `message(id, research_id, role, content, created_at)`
  - `finding(id, research_id, title, url, summary, source, found_at, dedupe_hash, dismissed)`
  - `run(id, research_id, started_at, status, cost_cents, new_findings)`
  - `api_key`
  - Additions: `research.unread` (bool) and `research.last_activity_at`. `finding` has a unique constraint on (research_id, dedupe_hash).

**Web UI (M2 on mock data, then wired in M3)**
- R5: Landing page shows "What do you want to research?" and an input. Submitting creates a research and navigates to `/r/<id>`.
- R6: Sidebar lists all researches, each with title, last activity, an unread dot and a watch on/off indicator. A "New research" button sits at the top. The list is sorted by last activity.
- R7: Thread page `/r/<id>` has chat messages (owner and agent), streamed agent answers (SSE), and a follow-up input.
- R8: Findings panel lists findings with title, summary and a clickable source link. Each finding can be dismissed.
- R9: Watch settings let the owner toggle the schedule on/off, set the frequency (presets: every 6h, daily, weekly), pause, and delete (with confirm).
- R10: The unread dot clears when the thread is opened.

**Research engine (M3)**
- R11: The agent loop uses the Claude API with a Tavily search tool. It streams tokens to the UI and persists the user and assistant messages.
- R12: Every finding saved has a non-empty valid http(s) URL. Findings without a URL are rejected in code. Claims without a source appear only as chat prose, never as findings.
- R13: `dedupe_hash` = sha256 of the normalized URL (lowercased host, tracking params and fragment stripped) plus a hash of the normalized title/summary. A finding is skipped if the URL or the content hash already exists for that research.

**Watches (M4)**
- R14: A scheduler (APScheduler with a Postgres job store, or a DB-polling worker) runs enabled watches when due. Each execution writes a `run` row with status `running|ok|capped|error` and the `cost_cents` and `new_findings` counts.
- R15: A run reports only findings not already stored. If `new_findings == 0`, no alert is sent and no message is added.
- R16: Per-run caps from env: `RUN_BUDGET_CENTS` (recommended 50) and `RUN_MAX_SEARCH_CALLS` (recommended 8). Cost is computed from token usage and search calls, in integer cents with no floats. Hitting a cap stops the run, marks it `capped`, keeps the findings already saved, and does not auto-retry. The next attempt happens only at the next scheduled time.
- R17: Restart safety. A run is claimed atomically (DB row lock or unique key on research_id + scheduled slot), so a restart or two workers never double-fire. On startup, stale `running` runs are marked `error`.
- R18: Run history is visible in the thread (list of runs with time, status, cost, new count).

**Telegram (M5)**
- R19: A separate bot token. Messages from `OWNER_CHAT_ID` only. A text message creates a research (and optionally a watch via a reply or button), then replies with an [Open] link. All other chats are ignored.
- R20: An alert is sent after a run with new findings. It shows the count and top 3 titles with links, plus inline buttons [Open] (URL button to `{PUBLIC_BASE_URL}/r/<id>`), [Pause watch], [Dismiss].
- R21: `callback_data` contains only an action and IDs (e.g. `pause:<research_id>`, `dismiss:<research_id>`), never content, and stays under 64 bytes. Callbacks are re-checked against the owner chat ID.
- R22: Dismiss marks that alert's findings `dismissed=true`. Pause sets `watch_enabled=false`.

**Public API (M6)**
- R23: `POST /api/v1/researches` {topic, watch?} creates a research and starts the run. `GET /api/v1/researches` and `GET /api/v1/researches/{id}` read them.
- R24: `GET /api/v1/researches/{id}/findings?since=<ISO8601>` returns `[{title, url, summary, found_at}]`, excluding dismissed findings.
- R25: `GET /api/v1/digest?topic=&days=` returns 3–5 ranked themes, each with a title, a one-line rationale and 2 or more supporting links. It is built from stored findings plus a capped research run. It is subject to the R16 caps. Days default to 7.
- R26: OpenAPI docs at `/docs`, with Bearer auth declared in the schema.

## Non-functional requirements & invariants
- **Access:** The UI is behind owner login, Telegram is owner-chat-only, and the API needs a valid key. Add tests asserting 401 on every protected route, and that a revoked key and a foreign chat ID are rejected.
- **Citations:** Findings must have a source URL (DB NOT NULL plus a validator, and tested).
- **Dedupe:** A run never re-reports a stored finding and never sends an empty alert (tested).
- **Cost:** Money is integer cents everywhere (DB integer columns, no float). The run budget and search-call caps are enforced and tested. Capped runs are not retried.
- **Keys:** API keys are stored hashed and shown once. Never log keys, the password or tokens.
- **Telegram:** Callback data carries IDs only.
- **Secrets:** Secrets live only in `.env`. `.env.example` is committed and `.env*` is gitignored (except the example). Required vars: `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`, `DATABASE_URL`, `TELEGRAM_BOT_TOKEN`, `OWNER_CHAT_ID`, `OWNER_PASSWORD_HASH`, `SESSION_SECRET`, `PUBLIC_BASE_URL`, `RUN_BUDGET_CENTS`, `RUN_MAX_SEARCH_CALLS`.
- **Scheduler:** Restart-safe with no double-fires (tested by simulating a restart).
- **Login:** Rate-limit login attempts (recommended 5 per minute per IP).
- **Performance:** The first streamed token appears within a few seconds. The sidebar loads fast on mobile.
- **Deployment:** Docker Compose with `api`, `web`, `postgres` and `bot` services. The UI is reachable only over Tailscale, with no public exposure.

## Stack
- **Specified:** Next.js App Router, TypeScript strict, Tailwind. FastAPI on Python 3.12 with Pydantic v2. Postgres. Claude via the Anthropic API. Tavily search (Exa is an alternative). APScheduler or a cron-style worker. Telegram bot with a separate token. Docker Compose on an Azure VM with Tailscale. No Clerk/Auth0.
- **Recommended:**
  - SQLAlchemy 2 + Alembic, psycopg3
  - python-telegram-bot or aiogram (long polling, since the host is private)
  - SSE for streaming
  - pytest + httpx for the backend
  - Vitest/Playwright for the frontend
  - Claude Sonnet-class model, configurable via env
  - Next.js proxies `/api` to FastAPI so the session cookie is same-origin

## UI
- **Screens (built UI-first on mock data in M2):** Login, Landing (new research), Thread `/r/<id>` (chat, streaming, Findings panel, watch settings, run history), Sidebar, and an API keys page (create, show once, revoke).
- **Phone (primary device):**
  - The layout is mobile-first. The sidebar is a slide-over drawer and Findings/Settings are a bottom sheet or tab.
  - The input is pinned to the bottom and handles the keyboard properly.
  - Touch targets are at least 44px.
  - There is no horizontal scroll.
  - Dark mode is the default.
  - There are no marketing pages.
  - Deep links to `/r/<id>` open directly after login and return to the target afterward.
  - A phone-viewport preview must be provided.

## Out of scope for the MVP
- Multi-user and teams
- Billing
- X/Twitter scraping
- Voice
- Email digests
- Mobile app
- Social posting (the separate LinkedIn bot does it)
- UI auth providers

## Open questions
- Budget defaults: are 50¢ per run and 8 searches per run right? Is there also a monthly or daily global spend cap?
- Which watch frequencies should be allowed (6h, daily, weekly are assumed), and should there be a minimum interval?
- Does `/digest` run live (it can take a while and cost money) or return a cached or async result? Assumed: synchronous, capped, cached for 24h per (topic, days).
- Should the Telegram [Dismiss] button dismiss that alert's findings (assumed) or only hide the alert message?
- Who can create API keys: the UI only, or also a CLI? Assumed both.
