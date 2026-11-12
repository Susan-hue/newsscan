# ADR-005: Use an AI model to find claims, then check them against fact-checks

- **Status:** Accepted (owner). Built 2026-11-12.
- **Decided by:** the owner, after Claude laid out three options.
- **Provider:** Groq. The owner chose it over Anthropic. The code hides the provider behind a small interface, so it can be swapped.

## The problem

Every scan said "Not enough evidence for a verdict", because no check based on outside evidence ever ran.
How do we make the app "AI-powered" in a way that produces real evidence?

## Options

| Option | Good | Bad |
|---|---|---|
| Fact Check API only | Real evidence, no AI cost | Finding claims with simple rules works badly on messy scans |
| **AI finds claims, then Fact Check API** (chosen) | Finds claims much better; the evidence still comes from published fact-checks | Needs a Groq key, sends the page text to an outside service, costs a little per scan |
| Local style classifier | Works offline | Can't count as evidence; would need a "fake probability", which this project forbids |

## What we do

An AI model reads the scanned text and lists up to 5 claims. Each claim is searched in Google's Fact Check
Tools. Only what Google returns counts as evidence.

## Rules

1. The AI never counts as evidence. It only suggests claims.
2. The scanned text is untrusted. It is sent as quoted data with an instruction to ignore any commands inside it.
   The reply is checked before use.
3. Both keys live only in `.env`, never in Git or logs.
4. Privacy: the scanned text leaves this machine. The feature is off unless every key is set, and the page says so.
5. If Groq or Google fails, the scan still finishes. That check shows as "not run".
6. Only the worker gets the keys.
7. Logs and metrics never contain claim or page text.
8. The wording is honest: "claims checked against published fact-checks". No accuracy number until we measure one.

## Decision on the band (owner, 2026-11-12)

Matches appear as evidence and move the band only to a neutral "Related fact-checks found". They never move it to
"reliable" or "weak". Google's search matches keywords, so a match can be about a different claim, and the ratings
are free text.

Rejected: letting the AI judge each match (the AI would then be evidence), and reading words like "false" in the
rating text (confidently wrong).

## Still open

- A monthly cost limit.
- Whether 5 claims per scan is right (it's the default, not yet confirmed).
- Whether sending the text should need a yes for each scan.

## What this means

The band can finally move, but only when someone has already fact-checked a claim on the page. Most pages will
still say "not enough evidence". That is the honest answer.
