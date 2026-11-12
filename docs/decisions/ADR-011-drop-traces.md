# ADR-011: Metrics and logs only. Traces are dropped.

- **Status:** Accepted
- **Decided by:** the owner, 2026-11-12. This replaces the scope part of [ADR-001](ADR-001-signal-scope.md).

## What changed

ADR-001 chose Option C: metrics, logs and traces. The owner now chooses **Option B: metrics and logs**.

## How this was decided

Claude recommended Option B back in ADR-001. After Claude explained what traces are, the owner agreed and chose B on
2026-11-12. So this follows Claude's recommendation; it is not an independent conclusion.

The owner's own reasons, if any, can be added here in their own words:

> _(optional, owner)_

## What this means

- Build order is now: **metrics (Steps A to F), then logs.** Nothing after that.
- The tracing milestone (M6, OpenTelemetry) is dropped. No trace tool will be added, and the app gets no tracing code.
- The rules from ADR-001 that still apply: build in order, finish each stage with one written failure
  investigation, check free RAM before each stage, keep the app small. The rule about one trace tool no longer matters.
- Logs are still the way to follow one scan: every log line already has a `scan_id`.
- Traces can come back later if the owner decides so. That would be a new ADR.
