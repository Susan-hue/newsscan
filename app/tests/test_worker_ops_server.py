import threading
import urllib.error
import urllib.request

import pytest
from prometheus_client import CollectorRegistry, Gauge, generate_latest

from newsscan.worker.ops_server import drop_api_only_metrics, make_server


@pytest.fixture()
def base_url():
    server = make_server(0)  # port 0: the OS picks a free port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, ""


def test_metrics_path_serves_metrics(base_url):
    status, body = get(base_url + "/metrics")
    assert status == 200 and "newsscan_stage_duration_seconds" in body


def test_healthz_says_alive(base_url):
    status, body = get(base_url + "/healthz")
    assert status == 200 and '"ok"' in body


@pytest.mark.parametrize("path", ["/", "/readyz", "/banana", "/metricsx", "/v1/scans"])
def test_every_other_path_is_404(base_url, path):
    # Before this fix the worker answered 200 with the metrics page for any path,
    # so a /healthz probe could never fail while the process was up.
    assert get(base_url + path)[0] == 404


def test_query_strings_do_not_change_the_route(base_url):
    assert get(base_url + "/healthz?x=1")[0] == 200
    assert get(base_url + "/banana?path=/metrics")[0] == 404


def test_the_worker_drops_the_queue_gauge_it_never_fills():
    registry = CollectorRegistry()
    queue = Gauge("newsscan_queue_depth", "Scan jobs waiting", registry=registry)
    Gauge("newsscan_other", "Something else", registry=registry)
    drop_api_only_metrics(registry, queue)
    text = generate_latest(registry).decode()
    assert "newsscan_queue_depth" not in text and "newsscan_other" in text
    drop_api_only_metrics(registry, queue)  # doing it twice must not fail
