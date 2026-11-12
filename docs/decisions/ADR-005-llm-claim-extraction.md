# ADR-005: LLM claim extraction feeding the Fact Check lookup (M4)

- **Status:** **Accepted (owner)** for the approach. Details marked *Open* are still to be decided. Built 2026-11-12.
- **Date:** 2026-11-12
- **Decided by:** the owner, chosen from the three options below after Claude laid out the trade-offs.
- **Provider (owner, 2026-11-12):** Groq, not Anthropic. Groq offers an OpenAI-compatible chat API, so the
  extractor sits behind a small interface and the provider can be swapped by changing one class.

## Question

Every scan currently reports "Not enough evidence for a verdict", because the only `evidence` signals
(`source_signals`, `claim_checks`) are `not_run`. How should the app become "AI powered" in a way that produces
real evidence?

## Options considered

| Option | Gain | Cost and risk |
|---|---|---|
| Fact Check Tools API only (the plan in ADR-004 row 10) | Real evidence signals; no LLM cost | Claim extraction would be rules, which is weak on messy OCR text |
| **LLM extracts claims, then Fact Check API** (**chosen**) | The model finds checkable claims far better than rules; the verdict still rests on external fact-checks | Needs an LLM API key (Groq); OCR text leaves the machine; per-scan cost; LLM output is a helper, never evidence |
| Local ML style classifier | Offline, nothing leaves the machine | Only `heuristic` signals, cannot move the band; a "fake probability" is forbidden; no training data |

## Decision

Add a claim-extraction stage that calls an LLM, then look each claim up in the Google Fact Check Tools API.

## Guardrails (these follow from the project rules)

1. **The LLM is never evidence.** It only proposes claims. Only matches returned by the Fact Check API become
   `evidence` signals, so a hallucinated claim cannot move the band.
2. **OCR text is untrusted input.** It goes to the model as quoted data in a prompt that says to ignore any
   instructions inside it. Model output is validated (a short list of short strings) before use, and is never
   rendered as HTML or used in a shell or a file path.
3. **Two keys (Groq and Google Fact Check), both in `.env` only**, read through `config.Settings` (`NEWSSCAN_` prefix), never logged, never in
   Git. `.env.example` gets placeholders.
4. **Privacy, stated in the UI and the README:** the recognised text is sent to an outside service. Off by
   default; the feature runs only when the keys are set.
5. **Failure is a status, not a crash.** If the LLM or the API is down, over quota or unconfigured, the signal is
   `not_run` with a safe message, and the scan still finishes.
6. **Boundaries:** the stages live in `extract/` (claims) and `analysis/` (lookup and signals); network calls sit
   behind small interfaces like `OCREngine`, so tests use fakes and never reach the network.
7. **Metrics:** count and time the external calls with bounded labels (service, outcome). Never log claim text
   or OCR text.
8. **Honest wording:** the UI says what it does (claims checked against published fact-checks). Not "AI detects
   fake news", and no accuracy figure until one has been measured.

## Band rule (owner, 2026-11-12)

Matches show up as an `evidence` signal and move the band only to a neutral `related_fact_checks`, never to
reliable or weak. Reason: Google's search is keyword-based, so a match can be about a different claim, and
ratings are free text that cannot be safely mapped to true or false. Rejected: an LLM judging each match (it would
put the model on the evidence path) and keyword rules on rating text (confidently wrong).

## Open (owner to decide)

- Which Groq model for extraction (a small, cheap one is likely enough). Model names change, so it is a
  setting (`NEWSSCAN_GROQ_MODEL`) with no default; the owner picks it from Groq's current model list.
- Monthly cost ceiling. Claims per scan is 5 by default (`NEWSSCAN_MAX_CLAIMS_PER_SCAN`), not yet confirmed by the owner.
- Whether the OCR text may be sent at all for pages you consider sensitive (a per-scan opt-in is an option).

## Consequences

The band can finally leave `insufficient_evidence`, but only when a fact-check exists for a claim on the page.
Most pages will still say "not enough evidence", and that is correct: the fact-check database covers only
claims that someone has already reviewed.
