"""Celery application. Redis is the broker (the queue). Scan state lives in the database,
so no result backend is configured.

Run the worker with a thread pool, not the default process pool:

    celery -A newsscan.worker.celery_app:celery_app worker --pool=threads --concurrency=2

The heavy work happens in the Tesseract subprocess, which runs outside the Python GIL, so threads
give real parallelism. A single process also lets the worker expose one Prometheus endpoint with
all of its metrics (port NEWSSCAN_WORKER_METRICS_PORT, default 9101).
"""

import logging

from celery import Celery
from celery.signals import setup_logging, worker_ready
from prometheus_client import start_http_server

from newsscan.config import get_settings
from newsscan.observability import configure_logging

_settings = get_settings()

celery_app = Celery("newsscan", broker=_settings.redis_url, include=["newsscan.worker.tasks"])
celery_app.conf.update(
    task_always_eager=_settings.celery_always_eager,
    task_serializer="json",
    accept_content=["json"],
    # Acknowledge a job only after it finishes, so a crashed worker's job is redelivered.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 3600},
    worker_hijack_root_logger=False,
)


@setup_logging.connect
def _configure_logging(**_: object) -> None:
    configure_logging(_settings.log_level)


@worker_ready.connect
def _start_metrics_server(**_: object) -> None:
    start_http_server(_settings.worker_metrics_port)
    logging.getLogger("newsscan.worker").info(
        "worker metrics server started", extra={"port": _settings.worker_metrics_port}
    )
