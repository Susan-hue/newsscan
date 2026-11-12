# ADR-007: Build order for the metrics stage

- **Status:** Accepted
- **Decided by:** the owner. Claude proposed it and the owner agreed.
- **Date:** 2026-11-12

## Decision

| Step | What | Why here |
|---|---|---|
| A | Prometheus collects metrics from the API and the worker | Nothing else has data until this works |
| B | Grafana with one dashboard | To see what Prometheus collects |
| C | Blackbox Exporter checks `/healthz` and `/readyz` | Asks from outside: does it answer? |
| D | Node Exporter and cAdvisor | Shows the machine and containers, to tell app problems from machine problems |
| E | Alertmanager and alert rules | Good alerts need metrics you already understand |
| F | One written failure investigation | Closes the stage (ADR-001) |

One step per session. Each ends with a recap and updated status tables.

## Rules that still apply (from ADR-001)

- Check free RAM before each stage. On 2026-11-12 about 2.7 GiB was free.
- Prometheus, Grafana and Alertmanager only listen on `127.0.0.1`.
- No default or hard-coded passwords. Secrets go in `platform/.env`, which Git ignores.

## Gap found and fixed before Step C

The worker's port 9101 used to answer 200 with the metrics page for **any** path, so a `/healthz` check could never
fail while the process was up. Fixed on 2026-11-12 with the owner's approval: the worker now serves only `/metrics`
and `/healthz` (alive), and answers 404 to everything else. `/healthz` is liveness only. It does not check Redis
or the database, the same as the API's `/healthz`.
