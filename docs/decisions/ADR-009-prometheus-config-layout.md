# ADR-009: Where Prometheus's files go

- **Status:** Accepted
- **Decided by:** the owner. Claude recommended it and the owner chose it.
- **Date:** 2026-11-12

## Options

| Option | Good | Bad |
|---|---|---|
| **One `prometheus.yml` with targets written in it, plus a `rules/` folder** (chosen) | Small enough to understand every line; `rules/` is ready for Step E | Adding a target means editing the file and reloading |
| `prometheus.yml` plus target files Prometheus re-reads | Targets change without a restart | One more moving part for two targets |
| One flat file, no folders | Smallest start | Has to be reorganised when alert rules arrive |

## Decision

```
platform/prometheus/prometheus.yml   settings and the two targets (api:8000, worker:9101)
platform/prometheus/rules/           empty until Step E
```

Check every config with `promtool check config` before starting Prometheus.
