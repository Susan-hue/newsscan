# ADR-002: One codebase, with a separate worker

- **Status:** Accepted
- **Proposed by:** Claude. **Confirmed by:** the owner ("Modular monolith is perfect")
- **Date:** 2026-11-11

## The problem

How should the app be split into running parts?

## Options

| Option | Good | Bad |
|---|---|---|
| Everything in one process, as a background task | Simplest | OCR is slow and heavy, so it slows down web requests; work is lost on a restart; no queue to monitor |
| **One codebase, an API process plus a worker process, Postgres and Redis** (chosen) | A real queue to monitor; easy to build, test and run on a laptop; easy to split later | Two processes to run; you must keep the code's parts separate |
| Microservices, one per stage | Scale each part alone | Far more work and RAM for a one-person project; would starve the monitoring work |

## Decision

One codebase. Its folders match the pipeline stages (`ingest`, `extract`, `analysis`, `aggregate`). The worker
runs the same image as the API, with a different command.

## Why it fits

The app exists to be monitored. A queue, a worker, a database and a cache give the monitoring real things to watch
(queue length, time per stage, failures) without the app using more RAM than the monitoring.

## What this means

- The separation between folders is a habit, not a wall. `CLAUDE.md` has the rules (for example, `analysis` never
  imports from `api`), and a test checks them.
- Splitting a stage out later is a refactor, not a rewrite. Only do it with a real reason.
