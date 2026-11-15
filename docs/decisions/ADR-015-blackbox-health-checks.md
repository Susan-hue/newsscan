# ADR-015: Health checks with the Blackbox Exporter

- **Status:** **Proposed.** Claude chose this and the version (v0.27.0). The owner asked for Step C but didn't
  choose between options. **It isn't a joint decision.**
- **Date:** 2026-11-16

## The problem

Prometheus only reads the numbers the app gives out. If the API is down, those numbers vanish, and that is hard
to tell apart from "no traffic". Something has to visit the app from outside, like a user, and say up or down.

## Choice

The Blackbox Exporter visits three addresses every 15 seconds: the API's `/healthz` and `/readyz`, and the
worker's `/healthz`. A page is up when it answers with a 2xx status. Prometheus gets `probe_success` (1 or 0)
and `probe_duration_seconds`.

| Option | Good | Bad |
|---|---|---|
| **Blackbox Exporter** (chosen) | The standard tool, little to set up, checks from outside | One more container |
| Docker healthchecks only | Nothing new | Prometheus can't see the result or its history |
| A custom script | Does exactly what we want | We would write and keep a tool that already exists |

## Details

- No port is published. Only Prometheus talks to the exporter, on the shared network.
- It checks that an address answers, not that scans work. `/readyz` covers the database and Redis.
- Two dashboard panels were added: checks passing, and check response time.

## What was tested

All three checks report up (3 to 13 ms). With the worker stopped for 35 seconds, its check went to 0 and the
other two stayed 1. After the restart all three were 1 again.
**Not tested:** stopping the API or Postgres, a slow response, and alerts (they come in Step E).
