# Fake News Detection System

Upload a photo or scan of a newspaper page (image or PDF). The app reads the text with OCR,
registers the document, and returns a **credibility report**.

> **Status: milestone M1, a walking skeleton. Not production.**
> The whole path works end to end (upload, queue, OCR, register, analyse, report) and is tested,
> but the analysis is still shallow. See [What the report does and does not say](#what-the-report-does-and-does-not-say).

This app is also the **monitored workload for Project 1** (the observability platform: Prometheus,
Grafana, Alertmanager and friends). It is intentionally small and exposes metrics and structured logs
so the platform has something real to watch.

## What the report does and does not say

The system does **not** output "fake" or "real". Models that do that generalise badly to new
sources and topics, and a confident wrong label is worse than no label. Instead each report has:

- a **band** (`insufficient_evidence` or `related_fact_checks`; `weak_signals`, `mixed` and `reliable_signals` are reserved),
- a table of **signals**, each marked `quality`, `heuristic` or `evidence`, and `ok` or `not_run`,
- plain-language **limitations**.

Quality and heuristic signals always run (OCR confidence, ALL-CAPS ratio, exclamation density,
sensational phrases). They are context and **cannot move the band**.

**Claim checking (M4, [ADR-005](docs/decisions/ADR-005-llm-claim-extraction.md))** is the only evidence
source and is **off by default**. When `NEWSSCAN_GROQ_API_KEY`, `NEWSSCAN_GROQ_MODEL` and
`NEWSSCAN_FACT_CHECK_API_KEY` are all set in `.env`, the worker asks a Groq-hosted model to pick out checkable
claims and searches each one in Google's Fact Check Tools API. The model only proposes claims; it is never
evidence. If matches are found the band becomes `related_fact_checks` and each match is listed with its
publisher, the publisher's own rating text and a link. The band does **not** say the page is true or false:
matches come from a keyword search and can be about a different claim. With no match, or any failure, the
band stays `insufficient_evidence`. `source_signals` is still `not_run`.

**Privacy:** when claim checking is on, the recognised text is sent to Groq and the claims to Google. Keys
stay in `.env` (never in Git) and only the worker container receives them.

## Quick start (Docker Compose)

Requires Docker with the Compose plugin.

```bash
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
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest                       # no services needed; Tesseract tests skip if it is missing
ruff check . && ruff format --check .

redis-server &               # queue
alembic upgrade head         # creates ./newsscan.db (SQLite)
celery -A newsscan.worker.celery_app:celery_app worker --pool=threads --concurrency=2 &
uvicorn newsscan.main:app --reload
```

Settings come from environment variables with the `NEWSSCAN_` prefix (see `.env.example` and
`src/newsscan/config.py`).

## Layout

```
src/newsscan/
  api/        HTTP routes and response schemas
  worker/     Celery app and the one task
  ingest/     file validation, page loading, preprocessing, OCR, reading order
  extract/    text normalisation and fingerprint
  analysis/   signals
  aggregate/  signals -> report
  pipeline.py runs the stages for one scan
  models.py db.py storage.py config.py observability.py main.py
migrations/   Alembic
scripts/      demo page generator and a small upload client
docs/         architecture and decision records (ADRs)
```

More in [docs/architecture.md](docs/architecture.md). Decisions are in [docs/decisions/](docs/decisions/).

## Known limitations (read these)

- **OCR on real newspapers is unproven.** Tested only on synthetic pages. Multi-column ordering
  works on clean and slightly skewed synthetic pages and **fails at about 3 degrees of skew**.
  See [ADR-003](docs/decisions/ADR-003-ocr-engine.md).
- **Fact-checking only covers claims someone has already reviewed**, so most pages still end at
  `insufficient_evidence`. A satirical or invented page with no published fact-check looks the same as an
  honest one. Matches are keyword-based and can be off-topic. Claim picking by the AI model has been tried on a
  few samples, not measured.
- **No authentication, quotas or rate limits.** Fine on localhost, not on the internet.
- **Tracing is not built.** Metrics and JSON logs are; OpenTelemetry traces come in the platform's tracing stage.
- Uploaded files stay on disk in a volume. There is no retention or deletion policy yet.
