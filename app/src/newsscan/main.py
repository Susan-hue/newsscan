"""FastAPI application factory."""

import logging
import re
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from newsscan import __version__
from newsscan.api import health, scans
from newsscan.config import get_settings
from newsscan.observability import HTTP_REQUESTS, HTTP_SECONDS, configure_logging

WEB_DIR = Path(__file__).parent / "web"
logger = logging.getLogger("newsscan.http")

_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")
_MULTIPART_OVERHEAD = 1024 * 1024  # allowance for form boundaries around the file
_PAGE_CSP = "default-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"


def route_template(request: Request) -> str:
    """The URL with path parameters replaced by their names, e.g. /v1/scans/{scan_id}.

    Used as a metric label. Real ids would create one time series per scan, which overloads
    Prometheus, and unknown URLs are collapsed into one bucket for the same reason. We rebuild
    the template from the path parameters because FastAPI's matched route omits the router prefix.
    """
    path = request.url.path
    if path.startswith("/static/"):
        return "/static/{path}"
    if request.scope.get("route") is None:
        return "unmatched"
    for name, value in request.scope.get("path_params", {}).items():
        path = path.replace(str(value), "{" + name + "}", 1)
    return path


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="newsscan", version=__version__)
    app.include_router(health.router)
    app.include_router(scans.router, prefix="/v1")
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.middleware("http")
    async def observe(request: Request, call_next):
        start = time.perf_counter()
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if _REQUEST_ID.fullmatch(supplied) else uuid.uuid4().hex

        # Reject oversized uploads early, before the body is read. Clients that send no
        # Content-Length are not covered here: put a body limit on the reverse proxy too.
        declared = request.headers.get("content-length", "")
        too_big = (
            request.method == "POST"
            and declared.isdigit()
            and int(declared) > settings.max_upload_bytes + _MULTIPART_OVERHEAD
        )
        if too_big:
            response = JSONResponse({"detail": "The file is too large."}, status_code=413)
        else:
            try:
                response = await call_next(request)
            except Exception:
                logger.exception("unhandled error", extra={"request_id": request_id})
                response = JSONResponse({"detail": "Internal server error."}, status_code=500)

        elapsed = time.perf_counter() - start
        template = route_template(request)
        HTTP_REQUESTS.labels(request.method, template, str(response.status_code)).inc()
        HTTP_SECONDS.labels(request.method, template).observe(elapsed)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path == "/" or request.url.path.startswith("/static"):
            response.headers["Content-Security-Policy"] = _PAGE_CSP
        if template not in ("/healthz", "/metrics"):  # keep scrape noise out of the logs
            logger.info(
                "request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "route": template,
                    "status": response.status_code,
                    "duration_ms": round(elapsed * 1000, 1),
                },
            )
        return response

    return app


app = create_app()
