# Platform: the monitoring stack

A learning project that runs on one laptop. It is not production experience.
It watches the app in `app/`. We build metrics first, then logs. Traces were dropped (ADR-011).

## Run it

```bash
cd app && docker compose up -d              # the app first
cd ../platform
docker compose config -q                     # check the file
docker compose up -d                         # the monitoring stack
```

Prometheus: http://127.0.0.1:9090. Grafana: http://127.0.0.1:3000. Both are reachable from this computer only.

**First time only: make the Grafana password.** This writes a random password into `platform/.env` (Git ignores it)
without showing it. It never overwrites an existing file. Read the password by opening that file.

```bash
cd platform
[ -f .env ] || ( umask 077; printf 'GRAFANA_ADMIN_PASSWORD=%s\n' "$(openssl rand -hex 16)" > .env )
```

Log in to Grafana as `admin` with that password.

## After switching git branches

Switching or merging branches can replace folders, and a running container keeps looking at the old one. Grafana
then logs `no such file or directory` and stops seeing new files. After a branch switch, run:

```bash
cd platform && docker compose up -d --force-recreate
```

`scripts/check.sh` warns you if this has happened. Saved data is not lost: Prometheus keeps its history in a volume.

## The dashboard

The dashboard is a file made by a script, not clicked together. To change it:

```bash
cd platform
python3 grafana/make_dashboard.py     # edit the PANELS list in that file first
```

Grafana picks up the new file within about 10 seconds. Changes made in the Grafana screen are not saved to the repo.

## Progress (metrics stage)

| Step | What | Status |
|---|---|---|
| A | Prometheus collects metrics from the API and the worker | Done. Both targets are up and queries work. Not yet tried: restarts, a target going down, a day of data |
| B | Grafana with one dashboard | Done and checked: Grafana loads the 10-panel dashboard from a file, and every panel's query returns data (after one test scan). Not yet tried: a full restart from nothing, and the panels on a failed scan |
| C | Blackbox Exporter checks `/healthz` and `/readyz` | Done: all three checks report up, and a stopped worker showed 0. Not yet tried: stopping the API or the database |
| D | Node Exporter and cAdvisor | Not started |
| E | Alertmanager and alert rules | Not started |
| F | One written failure investigation | Not started |

## Decisions

Build order, scrape timing, file layout and networking are in ADR-007 to ADR-010. Health checks are in ADR-015 (Proposed).
Claude chose the Prometheus version (v3.5.0). You didn't decide it together.
