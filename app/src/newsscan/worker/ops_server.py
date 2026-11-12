"""The worker's small HTTP server: /metrics for Prometheus and /healthz for liveness.

prometheus_client's own start_http_server answers every path with the metrics page, so a probe of
/healthz could never fail while the process was up. This one answers only the two paths it knows.
/healthz says the process is alive and nothing more (same meaning as the API's /healthz).
"""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/metrics":
            self._send(200, generate_latest(), CONTENT_TYPE_LATEST)
        elif path == "/healthz":
            self._send(200, b'{"status": "ok"}', "application/json")
        else:
            self._send(404, b'{"detail": "Not found."}', "application/json")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Stay quiet: Prometheus calls this every 15 seconds and would flood the logs."""


def make_server(port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(("0.0.0.0", port), _Handler)  # 0.0.0.0 so other containers can reach it


def start_ops_server(port: int) -> None:
    server = make_server(port)
    threading.Thread(target=server.serve_forever, daemon=True, name="worker-ops").start()
