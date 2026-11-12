# ADR-004: Choices Claude made without you, waiting for review

- **Status:** **Proposed.** None of these were decided together. Claude picked them to keep building.
- **Date:** 2026-11-11

Big decisions should be made with the owner. These were made without a conversation, so they are listed here.
For each one: accept it, change it, or give it its own ADR. They get more expensive to change as code piles up.

| # | Choice | Why Claude picked it | Main alternative | Cost of changing later |
|---|---|---|---|---|
| 1 | **Celery with Redis** as the job queue | Widely used, with retries and redelivery built in | RQ or Dramatiq (simpler); a Postgres queue (one less service); a cloud queue | Medium: touches `worker/` and the enqueue call in `api/scans.py` |
| 2 | **Celery worker with threads** (`--pool=threads`) | OCR runs as a separate Tesseract process, and one process means one metrics port | Process pool (needs extra metrics setup) | Low |
| 3 | **Normal (not async) SQLAlchemy 2.x** | Simpler to get right; the heavy work is in the worker anyway | Async SQLAlchemy | Medium |
| 4 | **Postgres 16 plus Alembic** | The standard choice; migrations are a core skill | SQLite only (simpler, but not like production) | Low |
| 5 | **pypdfium2** to turn PDF pages into images | Installs with pip, no system tools, permissive licence | pdf2image plus poppler; PyMuPDF (AGPL licence, a problem if the code is ever shared or sold) | Low |
| 6 | **A plain HTML page** as the UI, not React | Keeps the app small while the monitoring is the focus | A React frontend (milestone M7) | None: it is a separate layer |
| 7 | **Uploads on a local volume** | Local, free | S3-style storage (MinIO locally, S3 in the cloud). `LocalStorage` is already a small class | Low |
| 8 | **No result store for jobs; scan status lives in the database** | The database is the source of truth and survives restarts | Celery result backend in Redis | Low |
| 9 | **The report is a band plus signals, never a "fake or real" label** | Trained classifiers do badly on new sources and topics; a confident wrong label does harm | A classifier next to the signals | Low: it would be one more signal |
| 10 | **Google's Fact Check Tools API for lookups** | Needs a key; gives the same results as Fact Check Explorer | Other fact-check datasets; searching the web | Done in ADR-005 |

Please go through the table and say which rows to keep. Anything you change gets its own ADR.
