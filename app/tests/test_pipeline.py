import pytest

from newsscan.db import session_scope
from newsscan.ingest.ocr import OCRFailed
from newsscan.models import Document, Report, Scan, ScanStatus
from newsscan.pipeline import run_scan
from newsscan.storage import LocalStorage
from tests.conftest import SAMPLE_TEXT, FakeEngine, make_image


@pytest.fixture()
def stored_scan(app_env):
    storage = LocalStorage(app_env.storage_dir)
    key = storage.save(make_image())
    with session_scope() as session:
        scan = Scan(input_kind="image", content_type="image/png", size_bytes=10, storage_key=key)
        session.add(scan)
        session.commit()
        yield session, scan.id, storage


def run(session, scan_id, storage, settings, engine):
    run_scan(session, scan_id, storage=storage, engine=engine, settings=settings)


def test_a_scan_is_registered_analysed_and_reported(stored_scan, app_env):
    session, scan_id, storage = stored_scan
    run(session, scan_id, storage, app_env, FakeEngine())

    scan = session.get(Scan, scan_id)
    assert scan.status == ScanStatus.DONE
    assert scan.started_at and scan.finished_at and scan.error is None

    document = session.query(Document).filter_by(scan_id=scan_id).one()
    assert document.text.startswith("The city council approved the new transit budget")
    assert document.page_count == 1
    assert document.ocr_engine == "fake"
    assert document.mean_confidence == 92.0
    assert len(document.text_sha256) == 64

    report = session.query(Report).filter_by(scan_id=scan_id).one()
    assert report.band == "insufficient_evidence"
    assert {s["name"] for s in report.signals} >= {"ocr_quality", "claim_checks"}


def test_an_ocr_failure_marks_the_scan_failed_and_leaves_no_partial_rows(stored_scan, app_env):
    session, scan_id, storage = stored_scan

    class Broken(FakeEngine):
        def recognize(self, image):
            raise OCRFailed("Reading the page took too long. Try a smaller or clearer image.")

    run(session, scan_id, storage, app_env, Broken())

    scan = session.get(Scan, scan_id)
    assert scan.status == ScanStatus.FAILED
    assert "took too long" in scan.error
    assert session.query(Document).filter_by(scan_id=scan_id).count() == 0
    assert session.query(Report).filter_by(scan_id=scan_id).count() == 0


def test_an_unexpected_error_does_not_leak_internals(stored_scan, app_env):
    session, scan_id, storage = stored_scan

    class Crashing(FakeEngine):
        def recognize(self, image):
            raise ZeroDivisionError("secret internal detail")

    run(session, scan_id, storage, app_env, Crashing())

    scan = session.get(Scan, scan_id)
    assert scan.status == ScanStatus.FAILED
    assert "secret" not in scan.error
    assert scan.error == "Something went wrong while processing the scan."


def test_running_a_finished_scan_again_does_nothing(stored_scan, app_env):
    session, scan_id, storage = stored_scan
    run(session, scan_id, storage, app_env, FakeEngine())
    run(session, scan_id, storage, app_env, FakeEngine(text="different text"))

    documents = session.query(Document).filter_by(scan_id=scan_id).all()
    assert len(documents) == 1
    assert documents[0].text == SAMPLE_TEXT  # the second, different run changed nothing


def test_an_unknown_scan_id_is_ignored(app_env):
    with session_scope() as session:
        run(session, "00000000-0000-0000-0000-000000000000", None, app_env, FakeEngine())


# --- claim checking (ADR-005): fakes only, no network ---

from newsscan.analysis.factcheck import FactCheck, FactCheckError, FakeFactCheckLookup  # noqa: E402
from newsscan.extract.claims import ClaimExtractionError, FakeClaimExtractor  # noqa: E402
from newsscan.pipeline import build_claim_services  # noqa: E402

MATCH = FactCheck(
    claim="Transit budget approved",
    publisher="Example Checker",
    url="https://example.org/check/1",
    title="Was the budget approved?",
    rating="Mostly true",
    review_date="2025-01-01",
)


def run_with_claims(session, scan_id, storage, settings, extractor, lookup):
    run_scan(
        session,
        scan_id,
        storage=storage,
        engine=FakeEngine(),
        settings=settings,
        extractor=extractor,
        lookup=lookup,
    )
    return session.query(Report).filter_by(scan_id=scan_id).one()


def claim_signal(report):
    return next(s for s in report.signals if s["name"] == "claim_checks")


def test_matches_move_the_band_to_related_fact_checks_and_are_listed(stored_scan, app_env):
    session, scan_id, storage = stored_scan
    claim = "The council approved the transit budget."
    report = run_with_claims(
        session, scan_id, storage, app_env, FakeClaimExtractor([claim]), FakeFactCheckLookup({claim: [MATCH]})
    )
    signal = claim_signal(report)
    assert report.band == "related_fact_checks"
    assert signal["status"] == "ok" and signal["value"] == 1.0
    assert signal["items"][0]["publisher"] == "Example Checker"
    assert signal["items"][0]["claim"] == claim
    assert "not a verdict" in report.summary


def test_no_matches_is_ok_but_the_band_stays_insufficient(stored_scan, app_env):
    session, scan_id, storage = stored_scan
    report = run_with_claims(
        session, scan_id, storage, app_env, FakeClaimExtractor(["A claim."]), FakeFactCheckLookup()
    )
    assert claim_signal(report)["status"] == "ok" and claim_signal(report)["value"] == 0.0
    assert report.band == "insufficient_evidence"
    assert "none matched" in report.summary


def test_no_claims_found_is_not_run(stored_scan, app_env):
    session, scan_id, storage = stored_scan
    report = run_with_claims(
        session, scan_id, storage, app_env, FakeClaimExtractor([]), FakeFactCheckLookup()
    )
    assert claim_signal(report)["status"] == "not_run"
    assert report.band == "insufficient_evidence"


class BrokenExtractor:
    def __init__(self, error):
        self.error = error

    def extract(self, text, limit):
        raise self.error


class BrokenLookup:
    def __init__(self, error):
        self.error = error

    def search(self, claim, limit=3):
        raise self.error


@pytest.mark.parametrize(
    "error", [ClaimExtractionError("The service could not be reached."), RuntimeError("secret")]
)
def test_an_extractor_failure_does_not_fail_the_scan(stored_scan, app_env, error):
    session, scan_id, storage = stored_scan
    report = run_with_claims(
        session, scan_id, storage, app_env, BrokenExtractor(error), FakeFactCheckLookup()
    )
    assert session.get(Scan, scan_id).status == ScanStatus.DONE
    assert claim_signal(report)["status"] == "not_run"
    assert "secret" not in claim_signal(report)["detail"]
    assert report.band == "insufficient_evidence"


@pytest.mark.parametrize("error", [FactCheckError("down"), RuntimeError("secret")])
def test_a_lookup_failure_does_not_fail_the_scan(stored_scan, app_env, error):
    session, scan_id, storage = stored_scan
    report = run_with_claims(
        session, scan_id, storage, app_env, FakeClaimExtractor(["A claim."]), BrokenLookup(error)
    )
    assert session.get(Scan, scan_id).status == ScanStatus.DONE
    assert claim_signal(report)["status"] == "not_run"
    assert "secret" not in claim_signal(report)["detail"]


def test_a_partial_lookup_failure_keeps_the_matches_and_says_so(stored_scan, app_env):
    session, scan_id, storage = stored_scan

    class Half:
        def search(self, claim, limit=3):
            if claim == "bad":
                raise FactCheckError("down")
            return [MATCH]

    report = run_with_claims(session, scan_id, storage, app_env, FakeClaimExtractor(["good", "bad"]), Half())
    assert report.band == "related_fact_checks"
    assert "1 of 2 lookups failed" in claim_signal(report)["detail"]


def test_without_services_claim_checks_stay_off(stored_scan, app_env):
    session, scan_id, storage = stored_scan
    run(session, scan_id, storage, app_env, FakeEngine())
    report = session.query(Report).filter_by(scan_id=scan_id).one()
    assert claim_signal(report)["status"] == "not_run" and "switched off" in claim_signal(report)["detail"]


def test_real_services_are_built_only_when_every_setting_is_present(monkeypatch):
    from newsscan.config import Settings

    for name in ("GROQ_API_KEY", "GROQ_MODEL", "FACT_CHECK_API_KEY"):
        monkeypatch.delenv(f"NEWSSCAN_{name}", raising=False)
    assert build_claim_services(Settings(_env_file=None)) == (None, None, None)
    full = Settings(_env_file=None, groq_api_key="a", groq_model="m", fact_check_api_key="b")
    extractor, lookup, assessor = build_claim_services(full)
    assert extractor is not None and lookup is not None and assessor is not None
