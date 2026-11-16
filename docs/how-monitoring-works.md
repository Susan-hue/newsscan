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
| **Every request** (any route, any status, including 429, 500 and 503) | [main.py:117-118](../app/src/newsscan/main.py#L117). It sits in one middleware that every request passes through, so no route can be forgotten |
| Rate-limited uploads | [main.py:90](../app/src/newsscan/main.py#L90) |
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
- [main.py:28](../app/src/newsscan/main.py#L28), `route_template`: turns `/v1/scans/123` into `/v1/scans/{scan_id}`. Without
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

Each `job_name` is one thing Prometheus visits. `scrape_interval: 15s` at the top means every 15 seconds.

| Job | What it reads |
|---|---|
| `newsscan-api`, `newsscan-worker` | the app's own numbers (`/metrics`) |
| `prometheus`, `alertmanager`, `grafana`, `loki`, `alloy` | the monitoring stack watching itself |
| `node` | the computer's CPU, memory and disk (Node Exporter), plus the per-container numbers (section 4) |
| `postgres`, `redis` | the database and the queue, from the inside |
| `health-checks` | Blackbox visiting the three health addresses. The `relabel_configs` under it swap the address, so Prometheus asks `blackbox:9115` and passes the real address as the target |

A job that can't be reached shows up as `up = 0`. That is how Prometheus itself tells you a target is gone.
Retention (15 days or 1 GB) is set by the `--storage.tsdb.retention` lines in
[docker-compose.yml](../platform/docker-compose.yml). The `alerting:` block near the top of `prometheus.yml` says where to send alerts.

## 4. The helpers ([docker-compose.yml](../platform/docker-compose.yml))

Find each one by its name in that file.

- **Blackbox** (`blackbox`, config in [blackbox.yml](../platform/blackbox/blackbox.yml)): visits an address like a user and
  records `probe_success` (1 or 0) and the time. It knows nothing about the app's insides.
- **Node Exporter** (`node-exporter`): reads the computer's files through a read-only mount of `/` and reports CPU, memory and
  disk. It also reads the folder `platform/textfile/` (next item).
- **The `docker stats` script** ([docker_stats.py](../platform/scripts/docker_stats.py)): runs on the computer every 15 seconds
  (a systemd timer, installed by [install_docker_stats_timer.sh](../platform/scripts/install_docker_stats_timer.sh)). It runs
  `docker stats`, turns the result into Prometheus text (`render`, which also skips a broken row instead of failing) and
  writes `textfile/docker_containers.prom` in one step (`write_atomically`). Node Exporter shows that file to Prometheus.
  Tests: [test_docker_stats.py](../platform/tests/test_docker_stats.py).
- **Postgres exporter** (`postgres-exporter`): logs in as the read-only `monitor` role made by
  [create_postgres_monitor_role.sh](../platform/scripts/create_postgres_monitor_role.sh). It can read Postgres's statistics, not your scans.
- **Redis exporter** (`redis-exporter`): asks Redis about itself.
- cAdvisor (`cadvisor`) is parked and does not run (see ADR-016).

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

## 7. Logs ([ADR-019](decisions/ADR-019-logs-self-monitoring-and-hardening.md))

- Every container writes its log to a file (Docker's `json-file` driver). Both compose files cap each at 3 files of
  10 MB (`x-logging` at the top), and add the service name to each line.
- **Alloy** (`alloy`, config in [config.alloy](../platform/alloy/config.alloy)) reads those files, pulls the service name out of
  each line (`stage.json`), and sends the lines to Loki. It does not need the Docker socket.
- **Loki** (`loki`, config in [loki.yml](../platform/loki/loki.yml)) stores them for 7 days (`retention_period`, with
  `retention_enabled: true`, otherwise nothing is ever deleted).
- **Grafana** reads them through [datasources/loki.yml](../platform/grafana/provisioning/datasources/loki.yml). The generated
  [newsscan-logs.json](../platform/grafana/dashboards/newsscan-logs.json) dashboard has warnings and errors per minute, and the
  latest log lines. Its panels come from `LOG_PANELS` in [make_dashboard.py](../platform/grafana/make_dashboard.py).
- The app writes one JSON object per line with `scan_id` and `stage`, so in Grafana's Explore you can search
  `{service="worker"} |= "<a scan id>"` to see one scan's whole journey.

## 8. Who watches the watchers

Nothing inside Docker can report that Docker, or Prometheus, is down. Two layers:

- **Inside:** rules in the `monitoring-itself` group of [alerts.yml](../platform/prometheus/rules/alerts.yml): Alertmanager unreachable,
  alerts failing to send, rules failing to run, logs not arriving.
- **Outside:** [stack_watchdog.py](../platform/scripts/stack_watchdog.py) runs on the computer every minute (a systemd timer). It checks
  that Prometheus and Alertmanager answer and are connected. Two failed minutes in a row, and it sends a message to the phone
  by itself, without Prometheus or Alertmanager. The decision logic is the pure function `step`, tested in
  [test_stack_watchdog.py](../platform/tests/test_stack_watchdog.py).

## 9. The safety net

[scripts/check.sh](../scripts/check.sh) runs the tests, the dashboard-is-current check, the port check (everything bound to `127.0.0.1`),
the Prometheus, Alertmanager, Loki and Alloy config checks, the alert rule tests, a check that the containers see the current
files, and a check that no real secret value is sitting in any file Git could commit.
[scripts/scan_images.sh](../scripts/scan_images.sh) (slower, needs internet) scans every image for known vulnerabilities.
See the [security review](security-review-2026-11-16.md).

## What is NOT tracked yet

- Everything runs on this laptop. If it is off or asleep, nothing is watched and nothing can alert you.
- No alert is tuned on real data yet: the thresholds are guesses.
- Logs are kept for 7 days, in a volume on this computer. They are not backed up.
