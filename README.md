# Fake News Detection System

Upload a photo or scan of a newspaper page (an image or a PDF). The app reads the text, saves the document,
and gives you a **credibility report**.

> **Status: working on a laptop, not production.**
> The whole path works and is tested: upload, queue, text reading (OCR), analysis, report. The analysis is still
> shallow, so read [what the report says](#what-the-report-does-and-does-not-say).

This app is also the thing the monitoring project watches (Prometheus, Grafana and so on). It is kept small on
purpose. It gives out metrics and structured logs so the monitoring has something real to look at.

## What the report does and does not say

The app never says "fake" or "real". A wrong answer given with confidence does more harm than no answer.
Each report has:

- a **band**: `insufficient_evidence` or `related_fact_checks`. (`weak_signals`, `mixed` and `reliable_signals`
  are saved for later.)
- a table of **signals**. Each is a `quality` check, a `heuristic` (a weak writing-style hint), or `evidence`
  (checked against something outside the text). Each is either `ok` or `not_run`.
- a short list of **limits**, in plain words.

The quality checks and hints always run: OCR confidence, share of ALL-CAPS words, exclamation marks, and
clickbait phrases. They give context but **can't change the band**.

**Claim checking** ([ADR-005](docs/decisions/ADR-005-llm-claim-extraction.md)) is the only source of evidence.
It is **off by default**. It turns on when `NEWSSCAN_GROQ_API_KEY`, `NEWSSCAN_GROQ_MODEL` and
`NEWSSCAN_FACT_CHECK_API_KEY` are all set in `.env`. Then the worker asks an AI model (on Groq) to pick out
claims, and looks each one up in Google's Fact Check Tools. The AI only suggests claims. It is never evidence.

If Google returns matches, the band becomes `related_fact_checks`. Each match shows who rated it, their own
words, and a link. The band does **not** say the page is true or false, because the search matches keywords and
a result can be about something else. With no matches, or if anything fails, the band stays
`insufficient_evidence`. `source_signals` is still not run.

The same AI also gives a **satire hint** ([ADR-006](docs/decisions/ADR-006-plausibility-cue.md)). It may point at
visible signs, like a joke byline or impossible numbers, and say why. It can't move the band, it can be wrong,
and it says nothing about whether the page is true.

**Privacy:** when claim checking is on, the scanned text goes to Groq and the claims go to Google. The keys stay
in `.env`, which Git ignores, and only the worker container gets them.

## Quick start (Docker Compose)

Requires Docker with the Compose plugin.

```bash
cd app
cp .env.example .env
# edit .env and set POSTGRES_PASSWORD (letters and digits only, e.g. `openssl rand -hex 24`)
docker compose up --build
```

Open <http://127.0.0.1:8000>, drop in a scan, and watch the report appear.

| Thing | Where | Notes |
|---|---|---|
| Web page and API | `127.0.0.1:8000` | API docs at `/docs` |
| API metrics | `127.0.0.1:8000/metrics` | Prometheus format |
| Worker metrics | `127.0.0.1:9101/metrics` | Prometheus format |
| Postgres, Redis | compose network only | deliberately **not** published to the host |

Everything published to the host is bound to `127.0.0.1`, so nothing is reachable from your LAN.

### Try it without a real scan

```bash
cd app
python scripts/make_demo_page.py demo.png      # draws a synthetic two-column page (an easy case)
python scripts/scan.py http://127.0.0.1:8000 demo.png
```

(`scripts/scan.py` needs `httpx`, which is installed with `pip install -e ".[dev]"`.)

## API

| Method and path | Purpose |
|---|---|
| `POST /v1/scans` | Upload one file (multipart field `file`). Returns `202` with `{id, status}`. |
| `GET /v1/scans/{id}` | Status, and once done the document text and report. |
| `GET /healthz` | Liveness. |
| `GET /readyz` | Readiness: database and queue reachable. |
| `GET /metrics` | Prometheus metrics. |

Accepted: JPEG, PNG, WebP, TIFF, PDF (decided by file contents, not by name or declared type),
default limit 10 MB, 10 pages, 40 megapixels.

```bash
curl -s -F file=@page.jpg http://127.0.0.1:8000/v1/scans
curl -s http://127.0.0.1:8000/v1/scans/<id>
```

## Development without Docker

Needs Python 3.12+, Tesseract (`sudo apt install tesseract-ocr`) and a Redis server.

```bash
cd app
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest                       # no services needed; Tesseract tests skip if it is missing
../scripts/check.sh          # every check in one go: tests, lint, migrations, compose files, dashboard, ports, secrets
ruff check . && ruff format --check .

redis-server &               # queue
alembic upgrade head         # creates ./newsscan.db (SQLite)
celery -A newsscan.worker.celery_app:celery_app worker --pool=threads --concurrency=2 &
uvicorn newsscan.main:app --reload
```

Settings come from environment variables with the `NEWSSCAN_` prefix (see `.env.example` and
`app/src/newsscan/config.py`).

## Layout

```
app/          the app (everything you build and run for the scanner)
  src/newsscan/
    api/        HTTP routes and response schemas
    worker/     Celery app and the one task
    ingest/     file checks, page loading, cleanup, OCR, column reading
    extract/    text cleanup, and the AI calls that find claims and satire hints (Groq)
    analysis/   signals, and the fact-check lookup (Google)
    aggregate/  signals -> report
    pipeline.py runs the stages for one scan
    models.py db.py storage.py config.py observability.py main.py
  tests/  migrations/  scripts/  Dockerfile  docker-compose.yml  pyproject.toml
platform/     the monitoring stack (Prometheus now; Grafana and more later)
docs/         architecture and decision records (ADRs), shared by both
```

More in [docs/architecture.md](docs/architecture.md). Decisions are in [docs/decisions/](docs/decisions/).

## Known limitations (read these)

- **OCR on real newspapers is unproven.** Tested only on synthetic pages. Multi-column ordering
  works on clean synthetic pages. On pictures of real multi-column pages, the words come out in the wrong order about
  a quarter of the time or more (scores in ADR-003: about 77% of words in order on 5 pictures). Tilted pages are now straightened first, which helps a lot, but only tested by
  tilting pictures on purpose, not on real tilted photos.
  See [ADR-003](docs/decisions/ADR-003-ocr-engine.md).
- **Fact-checking only covers claims someone has already reviewed.** Most pages still end at
  `insufficient_evidence`. A satire or invented page with no fact-check looks the same as an honest one.
  Matches can be off-topic. The AI's claim picking and satire hint were tried on a few samples, not measured.
  Satire that sounds believable is not caught.
- **No login.** Uploads are limited to 10 a minute and 100 a day per visitor ([ADR-013](docs/decisions/ADR-013-upload-rate-limit.md)), but anyone can still use the app. Fine on localhost, not on the internet.
- **No tracing, by choice.** The app gives out metrics and JSON logs. Traces were dropped ([ADR-011](docs/decisions/ADR-011-drop-traces.md)).
- **Old uploads are deleted after a set number of days, but it is off until you turn it on**
  ([ADR-014](docs/decisions/ADR-014-delete-old-uploads.md)). The text and report stay. Not yet tried on the real volume.

## Platform

A monitoring lab for this app lives in [`platform/`](platform/README.md). We build metrics first, then logs
([ADR-007](docs/decisions/ADR-007-platform-stage1-build-order.md), [ADR-011](docs/decisions/ADR-011-drop-traces.md)).
It is a learning project, not production.

| Step | Status |
|---|---|
| A Prometheus | Done and checked locally. Recap pending |
| B Grafana | Done and checked: 13-panel dashboard loads from a file |
| C Blackbox | Done: health checks for the API and worker |
| D Computer, containers, database, queue | Done: the computer, each container, Postgres and Redis ([ADR-016](docs/decisions/ADR-016-machine-and-container-metrics.md), [ADR-017](docs/decisions/ADR-017-container-database-and-queue-metrics.md)) |
| E Alerts | Built: 8 alert rules, Alertmanager, phone messages through ntfy ([ADR-018](docs/decisions/ADR-018-alerts-to-phone.md)). A test message was delivered. Not yet tried: a real failure, or the urgent path on your phone |
| F Failure investigation | Done once: Postgres was stopped on purpose ([write-up](docs/investigations/2026-11-16-postgres-outage.md)). Alerts reached the phone in about 2 minutes. Found 5 problems, 1 fixed |
