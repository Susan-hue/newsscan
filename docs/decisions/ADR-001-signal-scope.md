# ADR-001: Signal scope for Project 1 (metrics, logs, traces)

- **Status:** Accepted
- **Decided by:** the owner (Claude had recommended Option B)
- **Date:** 2026-11-11

## Question

How much of the observability triad should Project 1 cover?

## Options

| Option | Scope | Gain | Cost and risk |
|---|---|---|---|
| A | Metrics only | Fastest, lowest RAM, the core Prometheus and Grafana skills | Cannot show "why", only "what" |
| B | Metrics and logs | Adds the debugging workflow of going from an alert to the matching log lines (Loki) | More RAM and moving parts |
| **C** | **Metrics, logs and traces** | **Complete picture: one request followed across API, queue and worker** | **Most RAM and work; traces are the hardest to do well; real risk of the platform swallowing the time for everything else** |

Claude recommended **B** and invited the owner to challenge that. The owner chose **C**.

## Decision

**Option C.** Metrics, then logs, then traces, built in that order.

## Reasoning (owner)

> _TO BE WRITTEN by the owner, in their own words, one or two lines: why C over B? This is the line an
> interviewer will ask about._

## Guard rails agreed with the decision

The owner chose the wider scope, so these gates keep it from sinking the rest of the plan:

1. Build in order: metrics, logs, traces. Each stage is finished before the next starts.
2. Each stage ends with **one written failure investigation** (break something on purpose, find it using only
   that stage's tools, write up what you saw).
3. **Check RAM before starting each stage.** If the machine cannot take it, stop and revisit this ADR.
4. **One trace backend only.**
5. Keep the monitored app thin until the platform catches up.

## Consequences

- The app already emits Prometheus metrics and JSON logs with `scan_id`; traces are deliberately not built yet
  (milestone M6).
- Revisit this ADR if the RAM check in gate 3 fails.
