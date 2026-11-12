"""Liveness, readiness and metrics endpoints."""

import logging

import redis
from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from newsscan.config import get_settings
from newsscan.db import get_engine
from newsscan.observability import QUEUE_DEPTH

logger = logging.getLogger("newsscan.health")
router = APIRouter(tags=["ops"])

_CELERY_QUEUE = "celery"  # Celery's default queue name in Redis


def _redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, socket_timeout=1, socket_connect_timeout=1)


@router.get("/healthz")
def healthz() -> dict:
    """Liveness: the process is up. Deliberately checks nothing else."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz() -> Response:
    """Readiness: the dependencies this API needs are reachable."""
    checks: dict[str, str] = {}
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        logger.exception("database check failed")
        checks["database"] = "unavailable"
    try:
        _redis().ping()
        checks["queue"] = "ok"
    except Exception:
        logger.exception("queue check failed")
        checks["queue"] = "unavailable"

    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse(
        {"status": "ok" if healthy else "unavailable", "checks": checks},
        status_code=200 if healthy else 503,
    )


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    try:
        QUEUE_DEPTH.set(_redis().llen(_CELERY_QUEUE))
    except Exception:
        QUEUE_DEPTH.set(float("nan"))  # unknown, not zero
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
