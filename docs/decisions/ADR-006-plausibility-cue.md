# ADR-006: AI plausibility cue for satire and implausible pages

- **Status:** **Accepted (owner)**, 2026-11-12. Built the same day. Not yet measured.
- **Decided by:** the owner, chosen from four options after Claude laid out the trade-offs.

## Question

A satirical or invented page with no published fact-check looks exactly like an honest one: both end at
`insufficient_evidence`. (Found with a generated "Daily News" test page about moose exports.) What can the
app say about such pages?

## Options considered

| Option | Gain | Cost and risk |
|---|---|---|
| **AI plausibility cue, band unchanged** (**chosen**) | Points at visible markers (pun names, impossible figures, parody wording, watermarks) with reasons; one extra Groq call, no new service | The model can be wrong in both directions; puts the model closer to judging content, so it must stay a cue |
| Corroboration against other news sources | Closest thing to a real fix for invented news | New paid API, more privacy exposure, false alarms for genuine local stories; its own milestone |
| Measure first | Gives numbers for later decisions | Fixes nothing by itself |
| Leave it | No work | Satire still looks like an honest page |

## Decision

Add a second, separate Groq call that returns `possible` or `none` plus up to 3 short reasons. It is stored as
a `heuristic` signal named `plausibility_cue`.

## Guardrails

1. **It cannot move the band.** Only `evidence` signals can (CLAUDE.md). The cue is `heuristic`, so this is
   structural, not a promise. If it says `possible`, one sentence is added to the summary so a reader sees it.
2. **It never judges truth.** The prompt forbids it, asks only for visible markers, and says to be
   conservative: dull or one-sided news is `none`.
3. **No reason, no flag.** A `possible` without a nameable reason is dropped to `none`.
4. **Wording:** "may be satire or implausible", never "fake". No accuracy claim.
5. **Same rules as ADR-005:** the page text is fenced as untrusted data and capped; output is validated; any
   failure is a `not_run` signal and the scan still finishes; same keys, only the worker has them; metrics use
   the bounded `service`/`outcome` labels; claim and page text are never logged.
6. **Runs only when claim checking is on** (the same three settings), so nothing new leaves the machine
   without the existing opt-in. The privacy notice already covers it.

## Consequences and limits

- It was tried on two samples only. That is not a measurement. It will miss subtle satire and may flag
  dry or quirky real writing. The test set from the "measure first" option is still worth building.
- It adds one more Groq call per scan (cost, a little latency).
- It does not detect invented news that reads plausibly. Only corroboration against other sources could, and
  that remains a separate, unbuilt option.
