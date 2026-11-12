# ADR-004: Defaults Claude chose, awaiting review

- **Status:** **Proposed.** None of these were decided jointly. Claude picked them to keep the build moving.
- **Date:** 2026-11-11

The rule for this project is that architectural decisions are made with the owner. These were chosen
without a conversation, so they are listed here to be accepted, changed, or promoted to their own ADR.
Each is cheap to change now and gets more expensive as code piles up.

| # | Choice | Why Claude picked it | Main alternative | Cost of changing later |
|---|---|---|---|---|
| 1 | **Celery with a Redis broker** for the queue | Mature and widely used in industry, with retries, acknowledgement and redelivery built in | RQ or Dramatiq (simpler); a Postgres-based queue (one fewer service); a cloud queue | Medium: touches `worker/` and enqueue calls in `api/scans.py` |
| 2 | **Celery worker with a thread pool** (`--pool=threads`) | OCR runs as a Tesseract subprocess outside the GIL, and one process gives one metrics endpoint | Prefork pool (needs multiprocess metrics handling) | Low |
| 3 | **Synchronous SQLAlchemy 2.x**, not async | Simpler to get right; FastAPI runs sync endpoints in a threadpool; the heavy work is in the worker anyway | Async SQLAlchemy | Medium |
| 4 | **Postgres 16 plus Alembic** | Standard relational choice; migrations are a core skill | SQLite only (simpler, but not what production looks like) | Low |
| 5 | **pypdfium2** to render PDF pages | Pure pip wheel, no system dependency, permissive licence | pdf2image plus poppler; PyMuPDF (AGPL licence, which matters if the code is ever shared or sold) | Low |
| 6 | **Static HTML page** as the UI, not React | Keeps the app thin while the platform is the focus | A React frontend (milestone M7) | None: it is a separate layer |
| 7 | **Uploads on a local volume** | Local-first, no cost | S3-compatible storage (MinIO locally, S3 in the cloud). `LocalStorage` is already behind a small class | Low |
| 8 | **No result backend; scan state in the database** | The database is the source of truth and survives restarts | Celery result backend in Redis | Low |
| 9 | **The report is a band plus signals, never a "fake or real" label** | Fine-tuned classifiers generalise poorly to new sources and topics; a wrong confident label is harmful | A classifier model alongside the signals | Low: it would be one more signal |
| 10 | **Fact-check lookups via Google's Fact Check Tools API** (planned, M4) | Needs an API key; returns the same fact-check results as Fact Check Explorer | Other fact-check datasets; building a retrieval step over web search | Not built yet |

Please go through the table and tell Claude which rows to keep. Anything you change gets a proper ADR.
