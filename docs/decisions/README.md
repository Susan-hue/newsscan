# Decision records (ADRs)

One short file per big decision: the problem, the options with good and bad points, who decided, and why.

Who decided is written down. Only a decision the owner made is called the owner's. If Claude picked something to
keep building, it is marked *Proposed* until the owner accepts or changes it.

| ADR | Topic | Status |
|---|---|---|
| [001](ADR-001-signal-scope.md) | What to monitor: metrics, logs and traces | Replaced by ADR-011 (traces dropped). Kept as history |
| [002](ADR-002-modular-monolith.md) | One codebase with a separate worker | Accepted (owner confirmed) |
| [003](ADR-003-ocr-engine.md) | OCR engine and column reading | **Proposed.** Owner decision needed |
| [004](ADR-004-defaults-pending-review.md) | Choices Claude made, waiting for review | **Proposed.** Review each row |
| [005](ADR-005-llm-claim-extraction.md) | AI finds claims, then Fact Check lookup | Accepted (owner). Cost limit and per-scan opt-in still open |
| [006](ADR-006-plausibility-cue.md) | AI satire hint | Accepted (owner). Built, not measured |
| [007](ADR-007-platform-stage1-build-order.md) | Build order for the metrics stage | Accepted (owner) |
| [008](ADR-008-prometheus-interval-and-retention.md) | How often to scrape, and how long to keep data | Accepted (owner). RAM figures to be measured |
| [009](ADR-009-prometheus-config-layout.md) | Where Prometheus's files go | Accepted (owner) |
| [010](ADR-010-platform-network-and-compose.md) | How the monitoring stack reaches the app | Accepted (owner) |
| [011](ADR-011-drop-traces.md) | Metrics and logs only; traces dropped | Accepted (owner), following Claude's recommendation |
| [013](ADR-013-upload-rate-limit.md) | Limit how many scans one visitor can upload | Accepted (owner) |
