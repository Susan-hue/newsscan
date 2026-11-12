# Platform: the monitoring stack

A learning project that runs on one laptop. It is not production experience.
It watches the app in `app/`. We build metrics first, then logs. Traces were dropped (ADR-011).

## Run it

```bash
cd app && docker compose up -d              # the app first
cd ../platform
docker compose config -q                     # check the file
docker compose up -d                         # the monitoring stack
```

Prometheus: http://127.0.0.1:9090 (this computer only).

## Progress (metrics stage)

| Step | What | Status |
|---|---|---|
| A | Prometheus collects metrics from the API and the worker | Done. Both targets are up and queries work. Not yet tried: restarts, a target going down, a day of data |
| B | Grafana with one dashboard | Not started |
| C | Blackbox Exporter checks | Not started |
| D | Node Exporter and cAdvisor | Not started |
| E | Alertmanager and alert rules | Not started |
| F | One written failure investigation | Not started |

## Decisions

Build order, scrape timing, file layout and networking are in ADR-007 to ADR-010.
Claude chose the Prometheus version (v3.5.0). You didn't decide it together.
