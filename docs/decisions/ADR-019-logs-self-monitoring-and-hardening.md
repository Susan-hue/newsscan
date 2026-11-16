# ADR-019: Logs, watching the watchers, newer versions and hardening

- **Status:** **Proposed.** The owner went to sleep and told Claude to "set up the whole thing, fix all problems and all
  vulnerabilities". That authorised the work. It did **not** choose between options, so every choice below is
  Claude's, not a joint decision. The owner should read it, and change anything they disagree with.
- **Date:** 2026-11-16

## What was asked

1. Find a way to track Prometheus itself.
2. Add logs.
3. Fix all problems and vulnerabilities.

## 1. Logs: Loki and Alloy

| Choice | Why | Other options |
|---|---|---|
| **Loki** stores the logs | Pairs with Grafana and Prometheus, light enough for a laptop, searches by label | Elasticsearch (heavy), plain files (no searching) |
| **Alloy** ships them | Grafana's current collector. The older Promtail has reached end of life | Promtail; Fluent Bit; Vector |
| Alloy **reads Docker's log files** | It needs no Docker socket (close to root access). Docker's files can be read by root, so Alloy runs as root, with all capabilities dropped and read-only mounts | Reading through the Docker socket: simpler labels, much more power |
| Keep logs **7 days** | A laptop disk. Cleanup needs `retention_enabled: true`, or Loki keeps everything | Longer: more disk |
| Name each line's service through a Docker label | Labels (`service`, `project`) let you search by service | Container ids: unreadable |

**A real problem found on the way:** Docker kept container logs with no size limit, so they grew forever. Every
container now keeps at most 3 files of 10 MB.

Known quirk: Loki 3.5.0 printed "negative structured metadata bytes" while rejecting very old log lines. It was
harmless, and it did not come back on Loki 3.7.10 (one "empty ring" message at start-up, then nothing).

## 2. Watching the watchers

- **Inside Prometheus:** it now scrapes itself, Alertmanager, Grafana, Loki and Alloy. New rules fire when
  Alertmanager can't be found, alerts or messages fail to send, rules fail to run, or no logs arrive for 10 minutes.
- **Outside Docker:** `scripts/stack_watchdog.py` runs every minute from a systemd timer. It checks that Prometheus and
  Alertmanager answer and are connected. After two failed minutes it sends a message to the phone by itself.

**The limit nothing here can fix:** if the whole computer is off or asleep, nothing runs and nothing can tell you.
A real fix needs something on another machine (a "heartbeat" service that alerts when it stops hearing from you).
That needs an account of yours, so it was not done.

## 3. Newer versions

The vulnerability scan (see `docs/security-review-2026-11-16.md`) found many fixable problems in the versions
that were pinned. All were moved to newer releases, staying on the same major version, so the risk of breaking
changes is small:

| Tool | Before | After |
|---|---|---|
| Prometheus | v3.5.0 | v3.16.0 |
| Grafana | 12.2.0 | 12.4.15 |
| Loki | 3.5.0 | 3.7.10 |
| Alloy | v1.10.0 | v1.22.0 |
| Alertmanager | v0.28.1 | v0.35.0 |
| Blackbox Exporter | v0.27.0 | v0.29.1 |
| Node Exporter | v1.9.1 | v1.12.1 |
| Redis exporter | v1.67.0 | v1.97.0 |
| Postgres exporter | v0.17.1 | v0.20.1 |
| Postgres, Redis | floating tags | same tags, re-pulled (16.16 and 7.4.12) |

Each config was checked with its new version first. After the move, Prometheus's history was intact, all 13 targets were
up, an urgent alert still delivered (tested with a throwaway copy), and a scan still worked.
The old images are still on the disk, so going back is only a change of version in the compose file.

## 4. Hardening

- App image: Debian security updates are applied during the build, and `pip` and `setuptools` are removed from the
  running image. Scan: 3 findings before, 0 after.
- Read-only root filesystem for the API, the worker and 8 monitoring containers (they write only to their own volumes
  and `/tmp`). Tested with an image scan and a PDF scan.
- `no-new-privileges` on Postgres and Redis too.
- The API now answers **503** when the database is down, not 500 (with a test), and writes one short log line instead of
  a traceback.
- Alertmanager's "Fixed" messages for critical alerts now arrive within a minute, not five.
- The `ServerErrors` alert needs 3 or more errors, not one (it gave a false alarm).

## What was not done, on purpose

- No change to anything that needs your accounts or money (an outside heartbeat service, email, WhatsApp).
- Nothing deleted. Old images, a stopped container and an unused volume are listed in the security review.
- No login for the app, no change to how uploads work.

## Tested

Configs and rules (13 checks in `scripts/check.sh`), the watchdog's logic (8 tests, no real outage was simulated because
it would have woken the owner), logs searchable by service and scan id, dashboards load, a real scan and a PDF scan.
**Not tested:** the watchdog sending a real urgent message, Postgres and Redis outages under the new versions, a reboot.
