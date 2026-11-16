# ADR-018: Alerts, and how they reach your phone

- **Status:** Accepted for "send alerts to the ntfy app" (the owner chose it). **Proposed** for the alert list,
  the thresholds, the timings and the versions, which Claude chose.
- **Date:** 2026-11-16

## The problem

Prometheus had the numbers but nothing told you when something broke. The owner wanted to be reached on their
phone, ideally loudly (WhatsApp, a call or a special sound were asked about).

## What was decided

| Question | Chosen | Other options |
|---|---|---|
| How do alerts reach the phone? | **ntfy** (the ntfy.sh service and its phone app) | WhatsApp through Meta's business API; a Telegram bot; Alertmanager's screen only |

Why not WhatsApp: it would arrive as a normal message with a normal sound. It can't call, and it can't override
silent mode. ntfy's top priority is built to do that on Android (not yet tested on this phone).

## How it works

Prometheus checks 8 rules (`prometheus/rules/alerts.yml`) and hands firing alerts to Alertmanager. Alertmanager
groups them and sends a message to ntfy.sh. ntfy turns Alertmanager's data into a readable title and text by
itself (a template in the address), so there is no extra bridge program.

| Alert | Severity | Fires when |
|---|---|---|
| HealthCheckFailing | critical | an address Blackbox visits fails for 1 minute |
| TargetDown | critical | Prometheus can't reach a target for 2 minutes |
| DatabaseDown | critical | Postgres doesn't answer for 1 minute |
| RedisDown | critical | Redis doesn't answer for 1 minute |
| DiskAlmostFull | warning | the disk is over 85% full for 5 minutes |
| ContainerNumbersStale | warning | the `docker stats` file is older than 2 minutes, or missing |
| ScansFailing | warning | 3 or more scans failed in 15 minutes |
| ServerErrors | warning | the API returned 3 or more 5xx errors in 5 minutes (it was "any error" at first, which gave a false alarm: see the investigation) |

Critical alerts go as ntfy priority 5 (urgent), wait 10 seconds before sending and repeat every hour. Warnings are
priority 3, wait 30 seconds and repeat every 4 hours. You also get a "Fixed" message when a problem ends.
**The thresholds are Claude's guesses, not measured on a real week of data.** Expect to tune them.

## Secrets

- The ntfy.sh topic name works like a password: anyone who knows it can read and send to it. It is made at
  random by `scripts/setup_ntfy.sh`, kept in `platform/secrets/` (Git ignores it) and is never printed.
- `scripts/check.sh` now looks for the real values of your keys, passwords and the topic in any file Git could
  commit, and fails if it finds one. It prints only file names.
- The secrets folder is mode 711 so the Alertmanager container (another user) can open the files. On a
  shared computer, other users could read a file if they knew its name. Fine on a one-person laptop.

## What was tested

- The 4 rule groups are tested with fake data (`promtool test rules`), and the test fails when a rule is broken.
- A test alert went through Alertmanager to ntfy.sh, and read back correctly: "PROBLEM: TestAlert", priority 3.
- A real failure (Postgres stopped on purpose): the alerts and the "Fixed" messages reached the owner's phone. See
  `docs/investigations/2026-11-16-postgres-outage.md`.
- **Not tested:** whether the urgent priority breaks through silent mode (the owner's phone is on vibration), and
  failures other than Postgres.

## Limits to know

- **Everything runs on this laptop.** If it is off or asleep, nothing is watched and nothing alerts you. If
  Prometheus itself dies, no alert says so.
- **ntfy.sh is a third party.** It sees the alert text (the descriptions in `alerts.yml`). Don't put secrets or
  personal data in them. The free service has limits and may change.
- Alertmanager keeps a failed alert group for 5 minutes before retrying. A short alert can end before that.
