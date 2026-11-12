# CLAUDE.md (app)

Rules for working in `app/`. The shared rules (the hard rules, the git workflow, how to work with the owner) are in
the root [CLAUDE.md](../CLAUDE.md). Read that first. Run every command below from the `app/` folder.
The code paths below are under `app/src/newsscan/`.

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

## Open decisions (ask before building on them)

- **ADR-003** OCR engine: Tesseract is a default, not a decision. Multi-column reading order is a known weak
  spot (fails at about 3 degrees of skew on synthetic pages); real scans have not been evaluated.
- **ADR-004** lists defaults chosen without the owner (Celery and Redis, sync SQLAlchemy, pypdfium2, static page,
  and others). Do not entrench them further without review.
- **ADR-001** is missing the owner's one-line reasoning for choosing Option C.

## Milestones

M1 walking skeleton (done). M4 claim checking is built (ADR-005, ADR-006: Groq finds claims, Google Fact Check
Tools looks them up; keys held in `.env`, never in Git). Next: **M2 OCR evaluation harness** on the owner's real
scans. Then M3 more inputs (text, URL with SSRF protection), M5 hardening (auth, rate limits, quotas, retention),
M7 optional React frontend. M6 OpenTelemetry traces was dropped (ADR-011). Details in `docs/architecture.md`.
