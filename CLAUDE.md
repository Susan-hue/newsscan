# CLAUDE.md

Guidance for Claude Code when working in this repository. Read this first, then `README.md`.
This repo has two parts. Read the file for the part you are working in:

- `app/` is the scanner app. Rules and commands are in [app/CLAUDE.md](app/CLAUDE.md) and `docs/architecture.md`.
- `platform/` is the monitoring stack. Notes are in [platform/README.md](platform/README.md).
- `docs/decisions/` holds the decision records (ADRs) for both.

## What this is

The **Fake News Detection System**: upload a photo or scan of a newspaper page (image or PDF), OCR it,
register the document, return a credibility **report** (a band plus signals plus limitations, never a bare
"fake or real"). It is also the **monitored workload for Project 1**, an observability platform (Prometheus,
Grafana, Alertmanager and others) the owner is building locally with Docker Compose. Keep the app small; the
platform is the focus.

The owner is a student learning Cloud and DevOps. **Explain what you do and why**, in small steps, and prefer
teaching over dumping code. Explain every non-obvious command before running it.

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

## Git workflow

Small branches, one purpose each, `pytest` and `ruff` green before opening a PR. Commit messages say what and why.
Do not commit `.env`, `data/`, `*.db`, or build output.
