import threading
import urllib.error
import urllib.request

import pytest

from newsscan.worker.ops_server import make_server


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
    assert status == 200 and "newsscan_queue_depth" in body


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
