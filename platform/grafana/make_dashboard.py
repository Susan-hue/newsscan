"""Writes the newsscan dashboard as a JSON file that Grafana loads on its own.

Run from the platform/ folder:   python grafana/make_dashboard.py
Check without writing:           python grafana/make_dashboard.py --check   (fails if the file is out of date)
To add a panel, add one line to PANELS and run it again. Grafana picks the file up within seconds.
"""

import json
import sys
from pathlib import Path

OUTPUT = Path(__file__).parent / "dashboards" / "newsscan-app.json"
DATASOURCE = {"type": "prometheus", "uid": "prometheus"}  # set in provisioning/datasources/prometheus.yml

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


dashboard = {
    "uid": "newsscan-overview",
    "title": "newsscan overview",
    "tags": ["newsscan"],
    "timezone": "browser",
    "schemaVersion": 41,
    "refresh": "30s",
    "time": {"from": "now-1h", "to": "now"},
    "panels": [panel(i, *p) for i, p in enumerate(PANELS, start=1)],
}

content = json.dumps(dashboard, indent=2) + "\n"

if "--check" in sys.argv:
    if not OUTPUT.exists() or OUTPUT.read_text() != content:
        sys.exit("The dashboard file is out of date. Run: python grafana/make_dashboard.py")
    print("dashboard file is up to date")
else:
    OUTPUT.write_text(content)
    print(f"wrote {OUTPUT} with {len(PANELS)} panels")
