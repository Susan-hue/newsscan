import os

from newsscan.api import health, scans
from newsscan.db import session_scope
from newsscan.models import Scan
from tests.conftest import SAMPLE_TEXT, make_image, make_pdf


def upload(client, data: bytes, name: str = "scan.png", content_type: str = "image/png"):
    return client.post("/v1/scans", files={"file": (name, data, content_type)})


def test_liveness_is_always_ok(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_readiness_reports_dependencies(client, monkeypatch):
    class Up:
        def ping(self):
            return True

    class Down:
        def ping(self):
            raise ConnectionError("no redis")

    monkeypatch.setattr(health, "_redis", lambda: Up())
    ok = client.get("/readyz")
    assert ok.status_code == 200 and ok.json()["checks"] == {"database": "ok", "queue": "ok"}

    monkeypatch.setattr(health, "_redis", lambda: Down())
    degraded = client.get("/readyz")
    assert degraded.status_code == 503 and degraded.json()["checks"]["queue"] == "unavailable"


def test_uploading_an_image_runs_the_whole_pipeline(client):
    response = upload(client, make_image("Council approves budget"))
    assert response.status_code == 202
    scan_id = response.json()["id"]

    scan = client.get(f"/v1/scans/{scan_id}")
    assert scan.status_code == 200
    assert scan.headers["cache-control"] == "no-store"
    body = scan.json()
    assert body["status"] == "done"
    assert body["input_kind"] == "image"
    assert body["document"]["text"] == SAMPLE_TEXT
    assert body["document"]["page_count"] == 1
    assert body["report"]["band"] == "insufficient_evidence"
    assert body["report"]["limitations"]


def test_uploading_a_pdf_works(client):
    response = upload(client, make_pdf(pages=2), "paper.pdf", "application/pdf")
    assert response.status_code == 202
    body = client.get(f"/v1/scans/{response.json()['id']}").json()
    assert body["status"] == "done" and body["input_kind"] == "pdf"


def test_the_content_type_header_is_not_trusted(client):
    response = upload(client, b"just some text, not an image", "scan.png", "image/png")
    assert response.status_code == 415


def test_empty_upload_is_rejected(client):
    assert upload(client, b"").status_code == 400


def test_damaged_image_is_rejected(client):
    assert upload(client, b"\x89PNG\r\n\x1a\n" + b"garbage" * 30).status_code == 422


def test_oversized_upload_is_rejected(client, app_env):
    too_big = b"\xff\xd8\xff" + os.urandom(app_env.max_upload_bytes + 10)
    assert upload(client, too_big, "big.jpg", "image/jpeg").status_code == 413


def test_hostile_file_name_does_not_reach_the_filesystem(client, app_env):
    response = upload(client, make_image(), "../../etc/passwd.png")
    assert response.status_code == 202
    stored = [p for p in app_env.storage_dir.rglob("*") if p.is_file()]
    assert len(stored) == 1 and stored[0].name != "passwd.png"
    assert app_env.storage_dir in stored[0].parents


def test_unknown_and_malformed_scan_ids_give_404(client):
    assert client.get("/v1/scans/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.get("/v1/scans/not-a-uuid").status_code == 404


def test_queue_outage_returns_503_and_records_the_failure(client, monkeypatch):
    def broker_down(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr(scans.process_scan, "delay", broker_down)
    response = upload(client, make_image())
    assert response.status_code == 503

    with session_scope() as session:
        scan = session.query(Scan).one()
        assert scan.status == "failed" and "queue is unavailable" in scan.error


def test_metrics_expose_scan_and_stage_series(client):
    upload(client, make_image())
    text = client.get("/metrics").text
    assert "newsscan_scans_submitted_total" in text
    assert 'newsscan_scans_finished_total{outcome="done"}' in text
    assert 'newsscan_stage_duration_seconds_count{stage="ocr"}' in text
    assert 'newsscan_http_requests_total{method="POST",route="/v1/scans",status="202"}' in text
    assert "newsscan_queue_depth" in text


def test_home_page_is_served_with_a_strict_content_security_policy(client):
    response = client.get("/")
    assert response.status_code == 200 and "Scan a paper" in response.text
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_report_schema_passes_fact_check_items_through_and_tolerates_old_reports():
    from newsscan.api.schemas import SignalOut

    base = {"name": "claim_checks", "kind": "evidence", "status": "ok", "value": 1.0, "detail": "d"}
    assert SignalOut.model_validate(base).items == []  # reports stored before M4 have no items
    item = {"publisher": "P", "rating": "False", "url": "https://a.example/x", "claim": "c"}
    assert SignalOut.model_validate({**base, "items": [item]}).items == [item]
