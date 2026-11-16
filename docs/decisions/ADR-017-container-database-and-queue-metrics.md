# ADR-017: Per-container numbers, and metrics for Postgres and Redis

- **Status:** Accepted for the first choice (the owner approved option 1). **Proposed** for everything else:
  Claude chose the exporters, the versions and the details, and the owner didn't decide them.
- **Date:** 2026-11-16

## The problem

After ADR-016, the stack knew about the computer but not about each container, and nothing about Postgres or
Redis. The owner asked for both.

## Per-container numbers (the owner approved this option)

A small script, `platform/scripts/docker_stats.py`, runs `docker stats` on the computer every 15 seconds and
writes the result to `platform/textfile/docker_containers.prom`. Node Exporter reads that folder and Prometheus
collects it. A user systemd timer runs it (`scripts/install_docker_stats_timer.sh`; `--remove` undoes it).

Why this and not a container with the Docker socket: nothing in Docker gets the socket (it is close to root access).
Other options were Telegraf, Docker's own endpoint, or a community exporter (see the chat; not built).

Limits:
- It lives **outside Docker**, so it only works while the timer is installed and the computer is on.
- If it stops, the old file stays. Its age shows as `node_textfile_mtime_seconds`, which an alert can watch (Step E).
- CPU is percent of one core, so a busy container can pass 100.

## Postgres and Redis (Claude's choice, Proposed)

Standard exporters: `postgres-exporter` v0.17.1 and `redis_exporter` v1.67.0, on the app network, no published
ports, run as non-root, all capabilities dropped.

- Postgres gets its **own login called `monitor`**, created by `scripts/create_postgres_monitor_role.sh`. It has
  only the `pg_monitor` role: it can read Postgres's statistics, not your tables. Tested: reading `scans` gives
  "permission denied". Its password is generated, kept in `platform/.env` (ignored by Git) and never printed.
- This **changed the live database**: one new login role. Undo it with `DROP ROLE monitor;`.
- Redis has no password in this setup, so its exporter needs none.

## What was tested

Prometheus collects all of it. Database size, connections, Redis memory and clients come through, and
`pg_up` and `redis_up` are 1. Not tested: the exporters when Postgres or Redis is down, and the timer after a
reboot.
