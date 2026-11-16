# Security review, 2026-11-16

**Done by:** Claude, overnight, while the owner slept. **Scope:** a local lab, not production. Everything listens on
`127.0.0.1` only (checked: no stack port is open on a public address).
**What this is:** automated scans plus a manual look. It is not a penetration test and it does not prove the app is safe.

## How to run it again

```bash
bash scripts/scan_images.sh     # scans every Docker image for known problems that already have a fix (slow, needs internet)
bash scripts/check.sh           # everything else, including that no secret value sits in a committable file
```

## Findings, and what was done

Counts are known **HIGH or CRITICAL** problems that already have a fix. "n/a" means it wasn't scanned before.

| Image | Before | After | What was done |
|---|---|---|---|
| The app (`newsscan:dev`) | 3 (zlib1g twice, setuptools) | **0** | Security updates at build, base image's pip and setuptools removed |
| Prometheus | 108 (v3.5.0) | 2 (v3.16.0) | Upgraded |
| Grafana | 160 (12.2.0) | 2 (12.4.15) | Upgraded |
| Redis | 7 | **0** | Re-pulled |
| Postgres | 45 | 26 | Re-pulled |
| Alloy | n/a | 0 | |
| Alertmanager, Blackbox | n/a | 2, 1 | Upgraded to the newest releases |
| Node Exporter | n/a | 16 | Newest release |
| Postgres exporter | n/a | 19 | Newest release |
| Redis exporter | n/a | 0 | |
| Loki | n/a | **not scanned** | The image can't be exported for scanning with this Docker |

**Python libraries of the app:** no known vulnerabilities (the only findings were in `pip` itself, now removed).

**What remains, and why it can't be fixed here:**
- The remaining 2 to 26 findings per image are Go libraries and the Go standard library compiled into the upstream
  tools (and `gosu` inside the Postgres image). They are fixed by the vendors' next releases, not by us.
  Re-run `scan_images.sh` now and then and move to newer versions.
- Real-world risk is low because nothing is reachable from outside the computer. Treat it as "not production".

## Hardening made (see ADR-019)

Read-only containers, `no-new-privileges`, capabilities dropped (already), log size caps (logs used to grow without
limit), database outage now a 503, a false-alarm alert fixed, a check that no real secret is in any committable file.

## Things the owner should know (not fixed)

| What | Why it matters | Suggested step |
|---|---|---|
| The app has **no login**. Anyone who can reach port 8000 can upload (rate limit: 10 a minute, 100 a day per visitor) | Fine on localhost, not on a network | Milestone M5 |
| `/docs`, `/openapi.json` and `/metrics` are open on the API port | Shows the API's shape and internal numbers to anyone who can reach it | Disable the docs and restrict `/metrics` before any real deployment |
| Prometheus and Alertmanager's pages have **no login** (Grafana does) | Anyone on this computer can open them. Alertmanager's page can silence alerts | Fine for one user. Add a reverse proxy with login if shared |
| Node Exporter sees the whole disk through a **read-only** mount of `/` | It can read file names and sizes everywhere | Accepted, written in ADR-016 |
| Alloy runs as **root** to read Docker's log files (capabilities dropped, read-only) | The alternative, the Docker socket, is worse | Accepted, ADR-019 |
| Logs hold whatever the containers print. The app never logs scan text or secrets, but Postgres and Grafana logs were not reviewed | Possible personal data in logs | Look through Explore once |
| The ntfy topic is the only secret protecting your phone alerts. Anyone who learns it can read and send alerts | The topic is long and random, and is kept out of Git | Make a new one with `setup_ntfy.sh` after deleting `platform/secrets/ntfy_topic` if you think it leaked |
| `platform/secrets/` is mode 711, so another user on this computer who knows a file's name can read it | Fine on a one-person laptop | |
| Python dependencies are **not locked** (version ranges, no lock file) | A rebuild may pick up different versions | Add a lock file |
| Docker volumes and the database are not encrypted or backed up | Data loss or disclosure if the laptop is lost or its disk fails | Backups are a separate task |

## Left on your computer by tonight's work (nothing was deleted)

Deleting Docker things needs your approval. These came from this project and are not used now:
- stopped container `newsscan-platform-cadvisor-1` (parked, ADR-016)
- unused volume `newsscan-platform_alloy-data` (empty, from a first attempt)
- old images: the previous versions of Prometheus, Grafana, Loki, Alloy, Alertmanager, Blackbox, Node Exporter, the Redis and
  Postgres exporters; three cAdvisor images; `grafana/loki:3.6.21`; `aquasec/trivy:0.67.2` (the scanner)
Other containers, volumes and images on this computer (atlasvision, senet, backend and others) were not touched.
