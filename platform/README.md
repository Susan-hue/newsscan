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

## First-time setup for the extra monitoring

Two things run outside the normal `docker compose up`. Do them once, with the app running:

```bash
bash platform/scripts/create_postgres_monitor_role.sh        # a read-only Postgres login for the exporter
bash platform/scripts/install_docker_stats_timer.sh          # per-container numbers every 15 s (--remove undoes it)
```

The first adds `POSTGRES_EXPORTER_PASSWORD` to `platform/.env`. Without it, `docker compose up` in `platform/` stops
and tells you to run the script. See ADR-017.

## Alerts to your phone (first time)

```bash
bash platform/scripts/setup_ntfy.sh                 # makes your secret topic. It prints nothing secret
cd platform && docker compose up -d                 # starts Alertmanager
cat platform/secrets/ntfy_topic                     # the topic name: type it into the ntfy app (see below)
bash platform/scripts/send_test_alert.sh            # a normal test alert
bash platform/scripts/send_test_alert.sh critical   # an urgent one
```

On the phone: install the **ntfy** app, tap +, choose the default server (ntfy.sh), and subscribe to that topic.
For urgent alerts to break through silent mode on Android, open the topic's settings and allow it to
override Do Not Disturb. Treat the topic like a password: don't paste it into chats, issues or commits.
Alertmanager's own page is at http://127.0.0.1:9093. See ADR-018 for the limits.

## Logs and the watchdog (first time)

Logs need nothing extra: `docker compose up -d` starts Loki and Alloy, and both compose files cap log sizes.
Open Grafana, then the **newsscan logs** dashboard, or Explore with the Loki source and a search like
`{service="worker"} |= "<a scan id>"`.

The watchdog checks Prometheus and Alertmanager from outside Docker and messages your phone if they are down:

```bash
bash platform/scripts/install_watchdog_timer.sh      # every minute (--remove undoes it)
python3 platform/scripts/stack_watchdog.py --dry-run # try it: sends nothing
```

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
| B | Grafana with one dashboard | Done and checked: Grafana loads the 20-panel dashboard from a file, and every panel's query returns data (after one test scan). Not yet tried: a full restart from nothing, and the panels on a failed scan |
| C | Blackbox Exporter checks `/healthz` and `/readyz` | Done: all three checks report up, and a stopped worker showed 0. Not yet tried: stopping the API or the database |
| D | The computer, each container, Postgres and Redis | Done: Node Exporter (computer), a `docker stats` script (each container; cAdvisor is parked, ADR-016), Postgres and Redis exporters (ADR-017). Not yet tried: a full disk, a reboot, Postgres or Redis going down |
| E | Alertmanager, 8 alert rules, messages to your phone through ntfy | Built. A test message was delivered. Not yet tried: a real failure, the urgent alert on your phone, or the "Fixed" message (ADR-018) |
| G | Logs (Loki and Alloy), watching Prometheus itself, newer versions, hardening | Built overnight by Claude: all Proposed, see ADR-019 and the [security review](../docs/security-review-2026-11-16.md). Not yet tried: a real reboot, Redis down, the watchdog sending an urgent message |
| F | One written failure investigation | Done: [Postgres stopped on purpose](../docs/investigations/2026-11-16-postgres-outage.md). Found 5 problems, 1 fixed. Other failures not tried |

## Decisions

Build order, scrape timing, file layout and networking are in ADR-007 to ADR-010. Health checks are in ADR-015 (Proposed). Computer and container metrics are in ADR-016.
Claude chose the Prometheus version (v3.5.0). You didn't decide it together.
