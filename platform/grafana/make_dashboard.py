"""Writes the newsscan dashboard as a JSON file that Grafana loads on its own.

Run from the platform/ folder:   python grafana/make_dashboard.py
To add a panel, add one line to PANELS and run it again. Grafana picks the file up within seconds.
"""

import json
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

OUTPUT.write_text(json.dumps(dashboard, indent=2) + "\n")
print(f"wrote {OUTPUT} with {len(PANELS)} panels")
