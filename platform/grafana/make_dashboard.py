"""Writes the newsscan dashboards as JSON files that Grafana loads on its own.

Run from the platform/ folder:   python grafana/make_dashboard.py
Check without writing:           python grafana/make_dashboard.py --check   (fails if the file is out of date)
To add a panel, add one line to PANELS (numbers) or LOG_PANELS (logs) and run it again.
Grafana picks the files up within seconds.
"""

import json
import sys
from pathlib import Path

DASHBOARDS_DIR = Path(__file__).parent / "dashboards"
DATASOURCE = {"type": "prometheus", "uid": "prometheus"}  # set in provisioning/datasources/prometheus.yml
LOKI = {"type": "loki", "uid": "loki"}  # set in provisioning/datasources/loki.yml

SECONDS = "s"  # Grafana picks the best size by itself: 9.2 ms for small values, 1.5 s for larger ones
PANELS = [
    (
        "Requests per second, by route",
        "sum by (route) (rate(newsscan_http_requests_total[1m]))",
        "{{route}}",
        "reqps",
    ),
    (
        "Server errors per second",
        'sum(rate(newsscan_http_requests_total{status=~"5.."}[1m])) or vector(0)',
        "errors",
        "reqps",
    ),
    (
        "Slowest 5% of requests (p95)",
        "histogram_quantile(0.95, sum by (le) (rate(newsscan_http_request_duration_seconds_bucket[5m])))",
        "p95",
        SECONDS,
    ),
    (
        "Scans waiting in the queue",
        'newsscan_queue_depth{job="newsscan-api"}',  # the worker also exposes it, but always as 0
        "waiting",
        "short",
    ),
    (
        "Scans finished since the worker started",
        "sum by (outcome) (newsscan_scans_finished_total)",
        "{{outcome}}",
        "short",
    ),
    (
        "Average seconds per stage, since the worker started",
        "sum by (stage) (newsscan_stage_duration_seconds_sum)"
        " / sum by (stage) (newsscan_stage_duration_seconds_count)",
        "{{stage}}",
        SECONDS,
    ),
    (
        "Calls to Groq and Google since the worker started",
        "sum by (service, outcome) (newsscan_external_calls_total)",
        "{{service}} {{outcome}}",
        "short",
    ),
    (
        "Uploads turned away since the API started",
        "sum by (window) (newsscan_rate_limited_total)",
        "over the {{window}} limit",
        "short",
    ),
    (
        "Health checks passing (1 = up, 0 = down)",
        'probe_success{job="health-checks"}',
        "{{instance}}",
        "short",
    ),
    (
        "Health check response time",
        'probe_duration_seconds{job="health-checks"}',
        "{{instance}}",
        SECONDS,
    ),
    (
        "Computer CPU in use",
        '100 * (1 - avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))',
        "CPU",
        "percent",
    ),
    (
        "Computer memory in use",
        "100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)",
        "memory",
        "percent",
    ),
    (
        "Disk space used",
        '100 * (1 - node_filesystem_avail_bytes{mountpoint="/"}'
        ' / node_filesystem_size_bytes{mountpoint="/"})',
        "disk",
        "percent",
    ),
    (
        "Memory used by each container",
        "newsscan_docker_container_memory_usage_bytes",
        "{{name}}",
        "bytes",
    ),
    (
        "CPU used by each container (100 = one full core)",
        "newsscan_docker_container_cpu_percent",
        "{{name}}",
        "percent",
    ),
    (
        "Database connections",
        'sum(pg_stat_database_numbackends{datname="newsscan"})',
        "open connections",
        "short",
    ),
    (
        "Database size",
        'pg_database_size_bytes{datname="newsscan"}',
        "newsscan database",
        "bytes",
    ),
    (
        "Redis memory (the queue)",
        "redis_memory_used_bytes",
        "memory",
        "bytes",
    ),
    (
        "Redis connected clients",
        "redis_connected_clients",
        "clients",
        "short",
    ),
    (
        "Alerts firing right now",
        'sum by (alertname) (ALERTS{alertstate="firing"})',
        "{{alertname}}",
        "short",
    ),
]


def panel(number: int, title: str, query: str, legend: str, unit: str) -> dict:
    return {
        "id": number,
        "type": "timeseries",
        "title": title,
        "datasource": DATASOURCE,
        "gridPos": {"x": 12 * ((number - 1) % 2), "y": 8 * ((number - 1) // 2), "w": 12, "h": 8},
        "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        "targets": [{"refId": "A", "datasource": DATASOURCE, "expr": query, "legendFormat": legend}],
    }


# The same words in every log line that means trouble: the app's JSON "level" field, or the word "error".
_TROUBLE = r'|~ `(?i)"level": ?"(warning|error|critical)"|error`'

# (title, kind, query). "graph" draws lines, "lines" lists log lines.
LOG_PANELS = [
    (
        "Warnings and errors per minute, by service",
        "graph",
        'sum by (service) (count_over_time({service=~".+"} ' + _TROUBLE + " [1m]))",
    ),
    ("Recent warnings and errors, all services", "lines", '{service=~".+"} ' + _TROUBLE),
    ("API and worker log", "lines", '{service=~"api|worker"}'),
]


def log_panel(number: int, title: str, kind: str, query: str) -> dict:
    if kind == "graph":
        return {
            "id": number,
            "type": "timeseries",
            "title": title,
            "datasource": LOKI,
            "gridPos": {"x": 0, "y": 8 * (number - 1), "w": 24, "h": 8},
            "fieldConfig": {"defaults": {"unit": "short"}, "overrides": []},
            "targets": [{"refId": "A", "datasource": LOKI, "expr": query, "legendFormat": "{{service}}"}],
        }
    return {
        "id": number,
        "type": "logs",
        "title": title,
        "datasource": LOKI,
        "gridPos": {"x": 0, "y": 8 * (number - 1), "w": 24, "h": 10},
        "options": {"showTime": True, "wrapLogMessage": True, "sortOrder": "Descending"},
        "targets": [{"refId": "A", "datasource": LOKI, "expr": query, "maxLines": 100}],
    }


def build(uid: str, title: str, panels: list[dict]) -> dict:
    return {
        "uid": uid,
        "title": title,
        "tags": ["newsscan"],
        "timezone": "browser",
        "schemaVersion": 41,
        "refresh": "30s",
        "time": {"from": "now-1h", "to": "now"},
        "panels": panels,
    }


DASHBOARDS = {
    "newsscan-app.json": build(
        "newsscan-overview", "newsscan overview", [panel(i, *p) for i, p in enumerate(PANELS, start=1)]
    ),
    "newsscan-logs.json": build(
        "newsscan-logs", "newsscan logs", [log_panel(i, *p) for i, p in enumerate(LOG_PANELS, start=1)]
    ),
}

stale = []
for name, dashboard in DASHBOARDS.items():
    path = DASHBOARDS_DIR / name
    content = json.dumps(dashboard, indent=2) + "\n"
    if "--check" in sys.argv:
        if not path.exists() or path.read_text() != content:
            stale.append(name)
    else:
        path.write_text(content)
        print(f"wrote {path} with {len(dashboard['panels'])} panels")

if "--check" in sys.argv:
    if stale:
        sys.exit(f"Out of date: {', '.join(stale)}. Run: python grafana/make_dashboard.py")
    print("dashboard files are up to date")
