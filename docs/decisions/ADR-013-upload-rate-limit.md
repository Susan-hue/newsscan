# ADR-013: Limit how many scans one visitor can upload

- **Status:** Accepted
- **Decided by:** the owner on the two choices below (Redis, and the numbers). Claude recommended both. The
  smaller rules under "Safe defaults" are Claude's choices, not joint ones.
- **Date:** 2026-11-13

## The problem

Anyone who can reach the API could upload scans without limit. Every scan makes 2 Groq calls and up to 5 Google
lookups, so a loop could quickly use up your free keys and fill the disk.

## Decisions

| Question | Chosen | Other option |
|---|---|---|
| Where are the counts kept? | **In Redis.** It is already running, counts survive restarts, and stay correct with more than one API container | In the API's memory: simpler, but resets on every restart |
| How strict? | **10 scans per minute and 100 per day** per visitor | 5 and 30 (strict) or 30 and 500 (loose) |

## Safe defaults (Claude's choice)

- Only `POST /v1/scans` is limited. Reading results, health checks and the web page are not.
- A visitor is the connection address, not a header like `X-Forwarded-For`, because a header can be faked.
  The address is stored as a short hash, never as plain text.
- Blocked uploads get HTTP 429, a `Retry-After` header and a message with the number of seconds to wait.
- The check runs before the upload is read, so a flood is turned away cheaply.
- A request blocked by the minute limit does not use up the day budget.
- If Redis or the limiter breaks, the upload goes through. Uploads need Redis for the queue anyway, and a broken
  limiter shouldn't take the whole service down.
- Metric: `newsscan_rate_limited_total{window}`, where window is `minute` or `day`. Both start at 0.
- Both limits can be changed or switched off (0) with `NEWSSCAN_RATE_LIMIT_PER_MINUTE` and `..._PER_DAY`.

## Limits of this

- On your laptop every request reaches the API from the same Docker address, so locally it acts like one visitor.
  Behind a real proxy the app would need to be told to trust the proxy's header. That is not built.
- Fixed windows allow a burst at a window edge (up to 20 in a few seconds across two minutes). Good enough here.
- This limits uploads. It is not a login. Anyone can still use the app.
