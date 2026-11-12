# CLAUDE.md

Guidance for Claude Code when working in this repository. Read this first, then `README.md` and
`docs/architecture.md`.

## What this is

The **Fake News Detection System**: upload a photo or scan of a newspaper page (image or PDF), OCR it,
register the document, return a credibility **report** (a band plus signals plus limitations, never a bare
"fake or real"). It is also the **monitored workload for Project 1**, an observability platform (Prometheus,
Grafana, Alertmanager and others) the owner is building locally with Docker Compose. Keep the app small; the
platform is the focus.

The owner is a student learning Cloud and DevOps. **Explain what you do and why**, in small steps, and prefer
teaching over dumping code. Explain every non-obvious command before running it.

## Commands

```bash
pip install -e ".[dev]"                 # install with test and lint tools
pytest                                  # no services needed (SQLite, eager Celery); Tesseract tests skip if absent
ruff check . && ruff format --check .   # lint and format check; `ruff format .` to fix formatting
alembic upgrade head                    # apply migrations (uses NEWSSCAN_DATABASE_URL)
alembic revision --autogenerate -m "what changed"   # then READ the generated file before committing it
alembic check                           # fails if models and migrations have drifted apart
docker compose up --build               # full stack; needs .env (copy .env.example)
docker compose config -q                # validate the compose file without starting anything
```

Before saying a change is done: `pytest`, `ruff check .`, `ruff format --check .` all pass, and if models changed,
`alembic check` passes.

## Layout and boundaries

```
api/        HTTP only: validate, store, insert row, commit, enqueue. Does not run pipeline stages.
worker/     Celery app and one thin task that calls pipeline.run_scan.
pipeline.py Orchestrates one scan: read_file, load, preprocess, ocr, normalise, register, analyse, report.
ingest/ extract/ analysis/ aggregate/    The stages. Plain functions: data in, data out.
models.py db.py storage.py config.py observability.py
scripts/    demo page generator and upload client (not part of the installed package)
```

Rules (enforced by `tests/test_boundaries.py`):

- Stage packages **never import** `api`, `worker`, `db`, `models`, `pipeline`, `storage` or `main`.
- `analysis` and `extract` import nothing else from the app.
- `api` may import `ingest` (cheap upload validation) and nothing else from the stages.
- Only `pipeline.py` touches the database for scan results, and it is the only place that runs stages in order.

OCR sits behind the `OCREngine` Protocol in `ingest/ocr.py`. New engines implement `recognize(image) -> OCRResult`.
Tests replace the engine by monkeypatching `ocr.get_ocr_engine` (see `tests/conftest.py`: `fake_ocr`).

## Conventions

- Python 3.12, type hints, `ruff` with line length 110. Small functions, docstrings that say **why**.
- Settings only through `config.Settings` (env prefix `NEWSSCAN_`). No `os.environ` reads elsewhere.
- Schema changes **only through Alembic**. Never edit an applied migration; add a new one.
- Every new behaviour gets a test. Bug fix means a failing test first.
- **Metrics labels must be bounded.** Use route templates, never raw paths, ids or user input as label values.
- Logs are JSON with `scan_id` and `stage` where relevant. **Never log OCR text, file contents or secrets.**
- OCR text is **untrusted input**. Never render it as HTML (the UI uses `textContent` only), never pass it to a
  shell, never use it to build file paths.
- User-facing errors are generic and safe. Internal details go to logs.
- A signal says what it measured and has a `kind` (`quality`, `heuristic`, `evidence`) and a `status`
  (`ok`, `not_run`). Only `evidence` signals may move the report band away from `insufficient_evidence`.
  Do not add a single "fake probability" number.

## Hard rules (from the owner)

1. **No secrets in Git.** `.env` is ignored; only `.env.example` with placeholders is committed. Never print a
   secret into logs, docs or commit messages.
2. **Never delete or prune Docker resources** (containers, images, volumes, networks, `docker system prune`,
   `docker compose down -v`) **without the owner's explicit approval** in that conversation. Volumes hold data.
3. **Monitoring and database ports stay bound to `127.0.0.1`.** Postgres and Redis are never published to the host.
4. **Architectural decisions involve the owner.** Present options with trade-offs and a recommendation, let the owner
   choose, then record an ADR in `docs/decisions/`. If you made a choice yourself, record it as *Proposed*
   (see ADR-004). **Never describe a choice as joint when you made it alone.**
5. **Be honest about maturity.** This runs locally. Do not describe it as production, and do not claim an
   unverified thing was verified. Say what was and was not tested.
6. Work in **small steps**. Do not add milestones the owner has not asked for.

## Open decisions (ask before building on them)

- **ADR-003** OCR engine: Tesseract is a default, not a decision. Multi-column reading order is a known weak
  spot (fails at about 3 degrees of skew on synthetic pages); real scans have not been evaluated.
- **ADR-004** lists defaults chosen without the owner (Celery and Redis, sync SQLAlchemy, pypdfium2, static page,
  and others). Do not entrench them further without review.
- **ADR-001** is missing the owner's one-line reasoning for choosing Option C.

## Milestones

M1 walking skeleton (done). Next: **M2 OCR evaluation harness** on the owner's real scans. Then M3 more inputs
(text, URL with SSRF protection), M4 claim checking via the Google Fact Check Tools API (needs an API key held in
`.env`, never in Git), M5 hardening (auth, rate limits, quotas, retention), M6 OpenTelemetry traces (when Project 1
reaches its tracing stage), M7 optional React frontend. Details in `docs/architecture.md`.

## Git workflow

Small branches, one purpose each, `pytest` and `ruff` green before opening a PR. Commit messages say what and why.
Do not commit `.env`, `data/`, `*.db`, or build output.
