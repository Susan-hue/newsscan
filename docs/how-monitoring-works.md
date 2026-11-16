# How the monitoring works

Read this top to bottom. It follows one number from the app to your screen.
Line numbers were right on 2026-11-16. If a file changed since, search for the name next to the number.

```
the app counts things  ->  the app shows them at /metrics  ->  Prometheus collects them every 15 s
   ->  Grafana asks Prometheus and draws graphs
Blackbox and Node Exporter are two more things Prometheus collects from.
```

## 1. The app counts things (`app/`)

Everything is defined once, in [observability.py](../app/src/newsscan/observability.py):

| Line | What | Kind |
|---|---|---|
| [27](../app/src/newsscan/observability.py#L27) | `HTTP_REQUESTS`: every request, by method, route and status | counter (only goes up) |
| [30](../app/src/newsscan/observability.py#L30) | `HTTP_SECONDS`: how long each request took | histogram (gives averages and p95) |
| [35](../app/src/newsscan/observability.py#L35) | `SCANS_SUBMITTED` | counter |
| [36](../app/src/newsscan/observability.py#L36) | `SCANS_FINISHED`, split into done and failed | counter |
| [37](../app/src/newsscan/observability.py#L37) | `EXTERNAL_CALLS`: calls to Groq and Google, ok or error | counter |
| [42](../app/src/newsscan/observability.py#L42) | `STAGE_SECONDS`: time per pipeline stage | histogram |
| [48](../app/src/newsscan/observability.py#L48) | `UPLOADS_DELETED`: files removed by the cleanup job | counter |
| [49](../app/src/newsscan/observability.py#L49) | `RATE_LIMITED`: uploads turned away | counter |
| [54](../app/src/newsscan/observability.py#L54) | `QUEUE_DEPTH`: scans waiting | gauge (goes up and down) |

A definition does nothing alone. The number only changes where the code calls it:

| What is counted | Where it happens |
|---|---|
| **Every request** (any route, any status, including 429 and 500) | [main.py:105-106](../app/src/newsscan/main.py#L105). It sits in one middleware that every request passes through, so no route can be forgotten |
| Rate-limited uploads | [main.py:89](../app/src/newsscan/main.py#L89) |
| Scan accepted | [api/scans.py:62](../app/src/newsscan/api/scans.py#L62) |
| **Every pipeline stage's time** | [observability.py:109](../app/src/newsscan/observability.py#L109), `timed_stage`. The pipeline wraps each stage in it ([pipeline.py:176-232](../app/src/newsscan/pipeline.py#L176)). It records the time even when the stage fails |
| Scan finished: done / failed | [pipeline.py:248](../app/src/newsscan/pipeline.py#L248) and [pipeline.py:261](../app/src/newsscan/pipeline.py#L261) |
| Calls to Groq and Google | [pipeline.py:113-156](../app/src/newsscan/pipeline.py#L113) |
| Old uploads deleted | [cleanup.py](../app/src/newsscan/cleanup.py), one count per deleted file |

**Lines that make sure nothing is missed**

- [observability.py:72-80](../app/src/newsscan/observability.py#L72): every known label is created at 0 at start-up.
  Without it, a counter only appears at its first event, and `rate()` misses that first event.
- [tests/test_metrics_start_at_zero.py](../app/tests/test_metrics_start_at_zero.py): checks those zeros exist. Its last
  test also reads `pipeline.py` and fails if someone adds a stage and doesn't add it to the list. That is the test that
  keeps the stage timing complete.
- [main.py:27](../app/src/newsscan/main.py#L27), `route_template`: turns `/v1/scans/123` into `/v1/scans/{scan_id}`. Without
  it, every scan would create a new line in Prometheus and slowly overload it.

## 2. The app shows the numbers

- **API:** [api/health.py:56](../app/src/newsscan/api/health.py#L56), `/metrics`. Just before answering it reads the queue length from Redis
  (line 59). If Redis is down it reports "unknown" (`nan`), not a false 0.
  [api/health.py:25](../app/src/newsscan/api/health.py#L25) `/healthz` (the process is up) and
  [api/health.py:31](../app/src/newsscan/api/health.py#L31) `/readyz` (the database and Redis answer).
- **Worker:** the worker is not a web server, so [worker/ops_server.py](../app/src/newsscan/worker/ops_server.py) is a tiny one.
  It answers `/metrics` (line 19) and `/healthz` (line 21), and nothing else. Line 50 removes the queue gauge there,
  because only the API knows the real queue length. Started from [celery_app.py](../app/src/newsscan/worker/celery_app.py).

## 3. Prometheus collects them ([prometheus.yml](../platform/prometheus/prometheus.yml))

| Lines | Job | What it does |
|---|---|---|
| 2 | `scrape_interval: 15s` | Collect every 15 seconds |
| 9-12 | `newsscan-api` | Reads `api:8000/metrics` |
| 14-17 | `newsscan-worker` | Reads `worker:9101/metrics` |
| 19-22 | `node` | Reads the computer's CPU, memory and disk from Node Exporter, plus the per-container numbers (section 4) |
| 24-27 | `postgres` | Reads the database's own numbers from the Postgres exporter |
| 29-31 | `redis` | Reads the queue's numbers from the Redis exporter |
| 33-49 | `health-checks` | Asks Blackbox to visit the three health addresses. Lines 43-49 swap the address, so Prometheus asks `blackbox:9115` and passes the real address as the target |

A job that can't be reached shows up as `up = 0`. That is how Prometheus itself tells you a target is gone.
Retention (15 days or 1 GB) is set in [docker-compose.yml](../platform/docker-compose.yml), lines 11-15.

## 4. The helpers ([docker-compose.yml](../platform/docker-compose.yml))

- **Blackbox** (line 33, config in [blackbox.yml](../platform/blackbox/blackbox.yml)): visits an address like a user and
  records `probe_success` (1 or 0) and the time. It knows nothing about the app's insides.
- **Node Exporter** (line 45): reads the computer's files through a read-only mount of `/` and reports CPU, memory and
  disk. It also reads the folder `platform/textfile/` (next item).
- **The `docker stats` script** ([docker_stats.py](../platform/scripts/docker_stats.py)): runs on the computer every 15 seconds
  (a systemd timer, installed by [install_docker_stats_timer.sh](../platform/scripts/install_docker_stats_timer.sh)). It runs
  `docker stats`, turns the result into Prometheus text (`render`, which also skips a broken row instead of failing) and
  writes `textfile/docker_containers.prom` in one step (`write_atomically`). Node Exporter shows that file to Prometheus.
  Tests: [test_docker_stats.py](../platform/tests/test_docker_stats.py).
- **Postgres exporter** (line 60): logs in as the read-only `monitor` role made by
  [create_postgres_monitor_role.sh](../platform/scripts/create_postgres_monitor_role.sh). It can read Postgres's statistics, not your scans.
- **Redis exporter** (line 71): asks Redis about itself.
- cAdvisor (line 83) is parked and does not run (see ADR-016).

## 5. Grafana draws them

- [datasources/prometheus.yml](../platform/grafana/provisioning/datasources/prometheus.yml): tells Grafana where Prometheus is
  (`http://prometheus:9090`). Without it, panels have no data.
- [dashboards/dashboards.yml](../platform/grafana/provisioning/dashboards/dashboards.yml): tells Grafana to load every file in
  `/etc/grafana/dashboards`. `allowUiUpdates: false` means a change made in the browser is not kept.
- [make_dashboard.py](../platform/grafana/make_dashboard.py): the `PANELS` list at the top is the **one place that decides what
  you see**. Each entry is a title, a Prometheus query, a legend and a unit. Line 99, `panel()`, turns an entry into a
  Grafana panel. Line 124 is the `--check` that fails if the saved file is out of date.
- [newsscan-app.json](../platform/grafana/dashboards/newsscan-app.json): the generated file. Never edit it by hand.

## 6. Alerts

- [alerts.yml](../platform/prometheus/rules/alerts.yml): 8 rules. Each has a plain `expr` (the test), a `for` (how long it must stay true)
  and a `severity`. Prometheus checks them every 15 seconds. `alerting:` in [prometheus.yml](../platform/prometheus/prometheus.yml) (line 5)
  hands firing ones to Alertmanager.
- [alertmanager.yml](../platform/alertmanager/alertmanager.yml): groups alerts so a burst is one message, picks the receiver by severity
  (critical is urgent and repeats hourly, the rest are normal) and sends "Fixed" messages when a problem ends.
- The destination address contains your secret ntfy topic, so it is not in the file. `url_file` reads it from
  `platform/secrets/`, made by [setup_ntfy.sh](../platform/scripts/setup_ntfy.sh). That folder is ignored by Git.
- [alerts_test.yml](../platform/prometheus/tests/alerts_test.yml): tests the rules with fake numbers, so you know a rule really fires.
- [send_test_alert.sh](../platform/scripts/send_test_alert.sh): sends a fake alert to check your phone.

## 7. The safety net

[scripts/check.sh](../scripts/check.sh) runs the tests, the dashboard-is-current check, the port check (everything bound to `127.0.0.1`),
the Prometheus and Alertmanager config checks, the alert rule tests, a check that the containers see the current files,
and a check that no real secret value is sitting in any file Git could commit.

## What is NOT tracked yet

- Nothing watches Prometheus itself, and everything runs on this laptop: if it is off or asleep, no alert can reach you.
- Logs are JSON lines on screen only. They are not collected anywhere (the Loki stage).
- Alert thresholds are guesses until there is real data. Nothing has been tested against a real failure yet.
