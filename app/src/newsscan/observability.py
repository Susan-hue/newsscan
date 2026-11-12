"""Logging and metrics. This is the app's observability contract with the monitoring platform.

Metrics (Prometheus):
  newsscan_http_requests_total{method,route,status}
  newsscan_http_request_duration_seconds{method,route}
  newsscan_scans_submitted_total
  newsscan_scans_finished_total{outcome}
  newsscan_stage_duration_seconds{stage}
  newsscan_queue_depth
  newsscan_external_calls_total{service,outcome}

Logs: one JSON object per line on stdout. Pipeline lines carry scan_id and stage.
"""

import json
import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "newsscan_http_requests_total", "HTTP requests handled by the API", ["method", "route", "status"]
)
HTTP_SECONDS = Histogram(
    "newsscan_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "route"],
)
SCANS_SUBMITTED = Counter("newsscan_scans_submitted_total", "Scans accepted by the API")
SCANS_FINISHED = Counter("newsscan_scans_finished_total", "Scans finished by the worker", ["outcome"])
EXTERNAL_CALLS = Counter(
    "newsscan_external_calls_total",
    "Calls to outside services made by the worker. service is groq or factcheck, outcome is ok or error",
    ["service", "outcome"],
)
STAGE_SECONDS = Histogram(
    "newsscan_stage_duration_seconds",
    "Time spent in each pipeline stage",
    ["stage"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)
QUEUE_DEPTH = Gauge("newsscan_queue_depth", "Scan jobs waiting in the queue")

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())


@contextmanager
def timed_stage(logger: logging.Logger, scan_id: str, stage: str) -> Iterator[None]:
    """Time a pipeline stage; record a histogram sample and a log line either way."""
    start = time.perf_counter()
    outcome = "ok"
    try:
        yield
    except Exception:
        outcome = "error"
        raise
    finally:
        elapsed = time.perf_counter() - start
        STAGE_SECONDS.labels(stage=stage).observe(elapsed)
        logger.info(
            "stage finished",
            extra={
                "scan_id": scan_id,
                "stage": stage,
                "outcome": outcome,
                "duration_ms": round(elapsed * 1000, 1),
            },
        )
