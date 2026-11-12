# ADR-006: An AI hint for satire and unlikely content

- **Status:** Accepted (owner), 2026-11-12. Built. Not measured.
- **Decided by:** the owner, from four options.

## The problem

A satire or made-up page with no fact-check looks the same as an honest one. Both say "not enough evidence".
We found this with a generated "Daily News" page about moose exports.

## Options

| Option | Good | Bad |
|---|---|---|
| **AI hint, band unchanged** (chosen) | Points at visible signs (joke names, impossible numbers) and says why; one more Groq call | The AI can be wrong either way, so it stays a hint |
| Check other news sources | The closest thing to a real fix | New paid service, more privacy cost, false alarms for local stories. A project of its own |
| Measure first | Gives real numbers | Fixes nothing by itself |
| Do nothing | No work | Satire still looks honest |

## What we do

A second Groq call answers "possible" or "none" plus up to 3 short reasons. It shows as a signal called
`plausibility_cue`.

## Rules

1. It can't move the band. Only evidence can. If it says "possible", one sentence is added to the summary.
2. It never says whether claims are true. It only points at visible signs, and defaults to "none".
3. No reason, no flag.
4. The wording is "may be satire or implausible", never "fake".
5. It follows the same safety rules as ADR-005 (untrusted text, checked replies, failures don't stop the scan).
6. It runs only when claim checking is on, so nothing new leaves the machine.

## Limits

- Tried on two samples only. That's not a measurement.
- It missed the pun in the byline "HAL E. TOSIS". One reason it gave ("garbled text") was really an OCR problem.
- It adds one Groq call per scan.
- It won't catch made-up news that sounds believable. That would need the "other sources" option.
