# Decision records (ADRs)

One short file per architectural decision: the question, the options with their trade-offs, who decided, and why.

**Who decided matters and is recorded.** A decision is only called a decision of the owner if the owner made it.
When a default was chosen by Claude to keep the build moving, it is marked *Proposed* until the owner accepts or
changes it.

| ADR | Topic | Status |
|---|---|---|
| [001](ADR-001-signal-scope.md) | Signal scope: metrics, logs and traces | Accepted (owner). Reasoning line still to be written |
| [002](ADR-002-modular-monolith.md) | Modular monolith with a separate worker | Accepted (owner confirmed) |
| [003](ADR-003-ocr-engine.md) | OCR engine and reading order | **Proposed.** Owner decision needed |
| [004](ADR-004-defaults-pending-review.md) | Defaults Claude chose, awaiting review | **Proposed.** Review each row |
| [005](ADR-005-llm-claim-extraction.md) | LLM claim extraction feeding the Fact Check lookup (M4) | Accepted (owner). Model, limits and opt-in still open |
