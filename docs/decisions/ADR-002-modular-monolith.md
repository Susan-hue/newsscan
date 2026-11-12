# ADR-002: Modular monolith with a separate worker

- **Status:** Accepted
- **Proposed by:** Claude. **Confirmed by:** the owner ("Modular monolith is perfect")
- **Date:** 2026-11-11

## Question

How should the Fake News Detection System be split into deployable parts?

## Options

| Option | Gain | Cost |
|---|---|---|
| Single process, work done in a FastAPI background task | Simplest | OCR is slow and CPU heavy, so it competes with request handling; work is lost on restart; nothing to monitor as a queue |
| **Modular monolith: one codebase, API process plus worker process, Postgres, Redis** | **Real async pipeline with a queue to monitor; simple to build, test and run on a laptop; module seams are ready if a split is ever needed** | **Two processes to run; some discipline needed to keep module boundaries clean** |
| Microservices (one service per stage) | Independent scaling, impressive diagram | Network calls, contracts, and deployment overhead for a one-person project; far more RAM; would starve the observability work of time and memory |

## Decision

The modular monolith. Package folders mirror the pipeline stages (`ingest`, `extract`, `analysis`,
`aggregate`). The worker runs the same image as the API with a different command.

## Why it suits this project

The app exists to be monitored. A queue, a worker, a database and a cache give the platform real things to
watch (queue depth, stage latency, failures) without the app costing more RAM than the platform.

## Consequences

- Module boundaries are conventions, not walls. `CLAUDE.md` states the rules (for example `analysis` never
  imports from `api`).
- Splitting a stage out later is a refactor, not a rewrite. Do it only with a concrete reason.
