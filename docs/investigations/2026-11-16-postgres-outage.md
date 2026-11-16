# Investigation: Postgres stopped on purpose

**Date:** 2026-11-16. **Done by:** Claude, with the owner watching their phone.
**What this is:** a planned test on the local setup, not a real incident. It shows whether the monitoring notices a
failure, how fast, and where it is weak. It is not evidence about production.

## What we did

Stopped the Postgres container (`docker compose stop postgres`: a stop, so no data was deleted). We timed what
Prometheus, Alertmanager and the phone did. During the outage we tried one upload. Then we started Postgres
again and watched it recover.

## Timeline

Times are seconds after the stop. A script recorded them, so they are real, not estimated.

| When | What happened |
|---|---|
| +10 s | `pg_up` became 0. The Postgres exporter noticed on its next 15 s look |
| +15 s | The `/readyz` health check began failing. `/healthz` kept passing, as designed: it only says the process is alive |
| +21 s | An upload got **HTTP 500 "Internal server error"** |
| +46 s | Three alerts were *pending* (waiting out their 1-minute rule): DatabaseDown, HealthCheckFailing, ServerErrors |
| +106 s | DatabaseDown and HealthCheckFailing were *firing* and Alertmanager had them |
| about +2 min | **Both reached the phone** (priority 5, urgent): about 2 minutes after the stop |
| +131 s | We started Postgres again |
| +136 s | `/readyz` passed again (5 s later). `pg_up` was 1 after 10 s |
| +166 s | Alertmanager had no alerts left |
| about +4.5 min after restart | "Fixed: DatabaseDown" and "Fixed: HealthCheckFailing" reached the phone |

An earlier version of our timing said the "Fixed" message came after 40 seconds. **That was wrong.** The message it
counted was the end of an old test alert that happened to finish at the same time.

After recovery: an upload was accepted and finished, and all earlier scans were still there (6 done).
Nothing was lost.

## What the monitoring did well

- It noticed in 10 to 15 seconds and told the phone in about 2 minutes. The 2 minutes is mostly the rules' own
  "stay broken for 1 minute" wait, which is there to avoid false alarms.
- Two different signals agreed: the database's own number and the outside check.
- It told us when it was fixed.
- Each alert said in plain words what was wrong.

## Problems found

| # | Problem | Status |
|---|---|---|
| 1 | **A false alarm from my own rule.** `ServerErrors` fired because of one 500 (our single test upload) and sent a warning to the phone. | **Fixed.** It now needs 3 or more server errors in 5 minutes. A test covers both cases |
| 2 | **The API says 500 when the database is down.** The honest answer is 503 "temporarily unavailable". A 500 looks like a bug in the app, and the message gives the user no hint to try again. | **Fixed** (same night, the owner asked for all fixes). 503 with a Retry-After header, one short log line, and a test that fails without the fix |
| 3 | **"Fixed" messages are slow, up to 5 minutes.** Alertmanager batches follow-up messages every 5 minutes (`group_interval`). | **Fixed.** 1 minute for critical alerts. The cost is more messages if something keeps flapping |
| 4 | **The logs are noisy and not collected.** While the database was down, each health probe wrote a long error trace (9 error lines in about 2 minutes). The logs only live on screen. | **Partly fixed.** Logs are now collected in Loki and searchable (ADR-019). The health check still writes a full traceback each probe |
| 5 | **Only the alert names tell you which part broke.** There is no dashboard panel for "what is failing now". | **Fixed.** A panel "Alerts firing right now" on the overview dashboard |

## What this test does not show

- **The sound.** The owner's phone is on vibration only, so we only know the alerts arrived and were seen. Whether an
  urgent alert breaks through silent mode on this phone is still untested.
- Only one failure was tried (Postgres). Redis down, the worker down, a full disk and a slow response were not.
- Everything ran on one laptop. If it were off, nothing would have alerted.
- The thresholds (1 minute, 85% disk and so on) are still guesses, not tuned on real data.
