# Limcity — Project History & Context Handoff

> Purpose: condensed context to resume work in a fresh session. Covers what was
> built, key decisions, and the environment quirks ("the odds") we fought through.

## Project overview

**Limcity** — Smart City Waste Management MVP (Entra21 graduation project, Blumenau, SC, Brazil).
Flow: citizen sends waste **photo + GPS** via WhatsApp → AI classifies the waste →
store geo-referenced data in PostGIS → serve **heatmaps** for public/private waste ops.

**Stack:** FastAPI (Python 3.10+ target; dev machine runs 3.14), PostgreSQL + PostGIS,
SQLAlchemy 2.0 async + GeoAlchemy2, Pydantic v2 / pydantic-settings, psycopg 3 (async),
Alembic, Meta WhatsApp Cloud API webhooks. Layered architecture:
`app/api` (thin routers) · `app/core` (settings, exceptions) · `app/db` · `app/models`
· `app/schemas` · `app/services` (business logic incl. classifier Strategy).

## Chain of thought (condensed timeline)

1. Reviewed project rules; audited repo (was just a hello-world `main.py` + `venv/` committed to git).
2. Raised design concerns (fragile BackgroundTasks, webhook signature/idempotency, LGPD, PostGIS specifics, missing foundations).
3. **Git hygiene + CI/CD:** added `.gitignore`, GitHub Actions CI (ruff/mypy/pytest on 3.11 & 3.12), Dependabot, split `requirements*.txt`, `pyproject.toml`, smoke test, `.env.example`, README.
4. **Layered app skeleton:** settings, exceptions, async DB session, `WasteReport` model (PostGIS POINT/4326 + GiST), schemas, `WasteClassifier` Strategy (ABC + Gemini stub + DI), report/whatsapp services, pipeline, webhook routes (verify + signed intake), wired `main.py`, `docker-compose` for PostGIS.
5. First commit `4a0225b` bootstrap; **pushed to `main`** (after auth drama — see odds).
6. **Database layer:** Alembic (`alembic.ini`, `migrations/env.py`, initial migration `0001` = PostGIS extension + `waste_reports`), brought up PostGIS container, applied & verified schema.
7. **Reports + heatmap APIs + dashboard:** read endpoints (`list`, `heatmap`, `stats`, `geojson`), Leaflet heatmap dashboard at `/dashboard`, demo seeder (`scripts/seed_demo.py`, 400 reports). Verified with a browser screenshot.
8. **WhatsApp testing tooling:** dev media bypass, signed sender script (`scripts/send_test_webhook.py`), CI-safe webhook tests. 9 tests passing.

## The Goods (what's working)

- **End-to-end pipeline works locally:** signed webhook → parse → idempotency → (dev media bypass) → placeholder classify → persist as PostGIS point → visible on heatmap.
- **Read APIs:** `/api/reports`, `/api/reports/heatmap` (grid-aggregated ~110m cells), `/api/reports/stats`, `/api/reports/geojson`.
- **Dashboard** `/dashboard`: live Leaflet heatmap over Blumenau, total, category legend + filter.
- **DB layer:** Alembic migration applied; `waste_reports` with SRID 4326 POINT, GiST index, unique `whatsapp_message_id` (idempotency), indexed `reporter_phone`.
- **Security/robustness in intake:** HMAC `X-Hub-Signature-256` verification, fast 200 ack, background processing, duplicate-message dedupe.
- **Quality gates green:** ruff + mypy (strict, 33 files) + pytest (9 tests). CI configured; Dependabot on.
- **Running now:** `limcity-db` container healthy on :5432; dev server via `run.py`; DB has 400 demo reports.

## The Odds (obstacles & how we solved them)

- **Shell tool sandbox unsupported on Windows** → every command returned "no exit status".
  Fix: run shell commands with elevated permissions (sandbox disabled). ~20s PowerShell startup overhead per command is normal.
- **PowerShell mangles nested quotes / special chars** (`<`, `{{ }}`, commas in `python -c`, `%{http_code}`).
  Workarounds: wrap in `cmd /c "..."`; avoid nested double quotes; avoid inline `python -c`; for `git commit` the harness appends a `Co-authored-by <...>` trailer that breaks `cmd /c`, so run `git commit` **directly** (not wrapped).
- **Python 3.14 wheels:** `asyncpg==0.30.0` has no 3.14 wheel and failed to compile (no MSVC).
  Fix: switched driver to **psycopg 3 (`psycopg[binary]`)**; URL is `postgresql+psycopg://`.
- **SQLAlchemy 2.0.36 incompatible with 3.14** (`Mapped[str | None]` union crash).
  Fix: upgraded to **SQLAlchemy 2.0.51**.
- **psycopg async + Windows Proactor loop** → `Psycopg cannot use the 'ProactorEventLoop'`.
  Fix: use a **SelectorEventLoop**. uvicorn's `run()` forces Proactor via `setup_event_loop()`, so `run.py` drives `Server.serve()` inside an explicit SelectorEventLoop; seeder does the same. (A policy set in `main.py` was too late/deprecated → removed.)
- **GeoAlchemy2 double spatial index:** `Geometry(...)` defaults `spatial_index=True`.
  Fix: set `spatial_index=False` on the model column; the GiST index is Alembic-owned.
- **mypy strict nits:** `scalar_one()` returns `Any` (wrapped in `int()`); empty-list literal needed annotation; `Depends()` in default → switched to `Annotated[...]`; excluded `migrations/` from ruff/mypy.
- **GitHub push auth:** remote was SSH (`git@github.com:reyroot/blumind-limcity.git`), repo didn't exist + local key not authorized; `gh` not installed. User created the repo, added the key, and **pushed manually** (SSH key has a passphrase the agent can't type). Note account/email mismatch: remote `reyroot` vs key email `reyhidalgobr@gmail.com` / account `reyrootoficial`.
- **Docker Desktop** engine wasn't running at first (needed manual start; `timeout` cmd doesn't work in the tool shell — used sleeps instead).

## ⚠️ Git state (IMPORTANT)

Only the bootstrap commit `4a0225b` is committed/pushed. **Everything after step 5 is UNCOMMITTED** on local disk:
- Modified: `main.py`, `app/api/router.py`, `app/core/settings.py`, `app/models/report.py`, `app/schemas/*`, `app/services/classifier/gemini.py`, `app/services/pipeline.py`, `app/services/report_service.py`, `pyproject.toml`
- Untracked: `alembic.ini`, `migrations/`, `app/api/routes/reports.py`, `app/static/`, `run.py`, `scripts/`, `tests/test_whatsapp_webhook.py`, `history.md`

Push requires the user (SSH passphrase). Suggest committing in logical chunks.

## Dev commands (Windows cmd)

```bat
docker compose up -d db                                REM start PostGIS
venv\Scripts\alembic upgrade head                      REM apply migrations
venv\Scripts\python -m scripts.seed_demo 400           REM seed demo data
venv\Scripts\python run.py                             REM run dev server (selector loop!)
venv\Scripts\python -m scripts.send_test_webhook       REM send a signed test webhook
venv\Scripts\ruff check . & venv\Scripts\mypy . & venv\Scripts\pytest -q
```

Dashboard: http://127.0.0.1:8000/dashboard · Docs: http://127.0.0.1:8000/docs

## Still placeholder / not done

- **AI classifier is a placeholder** (random category). Real Gemini/GPT vision call not wired.
- **Dev media bypass** active when `whatsapp_access_token` is unset (skips Graph API download).
- No citizen confirmation reply, retry/queue, auth/rate-limiting, or LGPD handling.
- No real Meta integration test (needs dev app + number + tunnel like ngrok/cloudflared).
- No DB-backed integration tests in CI (would need a Postgres service in the workflow).
- Dashboard has no date-range UI (API supports the filter).
- `settings.debug=True` makes SQLAlchemy echo SQL (noisy); consider decoupling.

## Suggested next steps

1. Commit & push the current work (logical chunks).
2. Implement the real Gemini classifier behind the existing Strategy.
3. Add dashboard date/time filters + optional marker layer.
4. Add PostGIS service to CI and DB-backed integration tests.
5. Harden: queue/retries, LGPD (image retention/consent), rate limiting.
