# Research Bot — BRD

A personal research assistant ("my own Claude for research"). I give it a topic; it researches, keeps watching on a schedule, and notifies me on Telegram. Each notification opens a ChatGPT-style web UI where every research is its own thread. It also exposes an HTTP API so other bots (first: the LinkedIn social bot) can use it.

Single user (me). Not multi-tenant.

## Core loop
topic → research thread created → agent researches (web search, citations) → findings saved → optional recurring watch → Telegram alert with button → opens that thread in the UI → I can keep chatting/asking follow-ups in the thread.

## UI (UI-first milestone, build on mock data)
- Layout like ChatGPT: left sidebar listing all researches (title, last activity, unread dot, watch on/off), "New research" button at top, main chat area on the right.
- Landing page: "What do you want to research?" input.
- Every research = its own page/URL (`/r/<id>`), created when the research is spawned (from UI, Telegram, or API).
- Thread page: chat messages (me + agent), streamed answers, a "Findings" panel with source links, and watch settings (schedule on/off, frequency, pause, delete).
- Telegram alert buttons deep-link to `/r/<id>`.
- Mobile-first (I use it from my phone), dark mode, no marketing pages.
- Examples of researches I will run: "new startups hiring AI engineers (Vancouver / remote)", "what's new in AI this week", "funding rounds in agent tooling".

## Components
1. **Web UI** — Next.js (App Router), TypeScript strict, Tailwind.
2. **API** — FastAPI (Python 3.12, Pydantic v2), Postgres.
3. **Research engine** — Claude (Anthropic API) agent loop with Tavily (or Exa) search. Streams responses to the UI.
4. **Scheduler** — recurring watches (APScheduler or cron-style worker). Each run only reports NEW findings (dedupe by URL + content hash).
5. **Telegram bot** — separate bot token. Create a research by messaging a topic; receive alerts with inline buttons [Open] [Pause watch] [Dismiss].
6. **Public API for other bots** — `/api/v1/*`, API-key auth, OpenAPI docs.

## Data model (minimum)
research(id, title, topic, created_at, watch_enabled, schedule, last_run_at), message(id, research_id, role, content, created_at), finding(id, research_id, title, url, summary, source, found_at, dedupe_hash, dismissed), run(id, research_id, started_at, status, cost_cents, new_findings), api_key(id, name, key_hash, created_at, revoked_at).

## HTTP API (for the social bot)
- `POST /api/v1/researches` {topic, watch?} → create research
- `GET /api/v1/researches` · `GET /api/v1/researches/{id}`
- `GET /api/v1/researches/{id}/findings?since=` → structured findings (title, url, summary, found_at)
- `GET /api/v1/digest?topic=&days=` → ranked topic candidates (3–5 themes with supporting links) — this is what the LinkedIn bot calls weekly.
- Auth: `Authorization: Bearer <api key>`; keys stored hashed, revocable.

## Invariants (enforced in code AND tested)
1. Only I can use it: UI behind login (single owner), Telegram obeys only my chat ID, API requires a valid key. Unauthenticated requests get 401.
2. Every finding stored has a source URL. No uncited claims presented as findings.
3. A watch run never re-reports a finding already stored (dedupe), and never sends an empty alert.
4. Cost control: each run has a hard budget cap (cents) and max search calls; runs that hit the cap stop and are marked, not retried forever. Money in integer cents, no floats.
5. API keys are stored hashed and are shown once at creation.
6. Telegram callback data carries IDs only, never content.
7. Secrets only in `.env`; `.env.example` committed; `.env*` gitignored.
8. Scheduler is restart-safe: a restart never double-fires a run.

## Milestones
- **M1** Backend skeleton + Postgres schema + auth (owner login, API keys) + health check.
- **M2 (ui: true)** Chat UI on mock data: sidebar, new-research landing, thread page, findings panel, watch settings. Phone preview.
- **M3** Research engine: Claude + Tavily agent loop, streaming into threads, citations, findings saved. Connect UI to real data.
- **M4** Watches: per-research schedule, new-findings-only diff, run history, cost caps.
- **M5** Telegram bot: create research from a message, alerts with [Open] deep link, pause/dismiss, owner-only.
- **M6** Public API for other bots (`/api/v1`), `/digest` endpoint, OpenAPI docs, API-key tests.

## Out of scope (v1)
Multi-user/teams, billing, X/Twitter scraping, voice, email digests, mobile app, social posting (that is the separate social bot).

## Deployment
Runs on my Azure VM (Docker Compose: api, web, postgres, bot). UI reachable privately via Tailscale so Telegram links open on my phone.

## Defaults I chose (change if wrong)
Claude via Anthropic API for reasoning, Tavily for search, Postgres, single-owner password login, Tailscale for private access, no UI auth provider (no Clerk/Auth0).
