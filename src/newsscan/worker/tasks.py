"""Celery tasks. Thin on purpose: all logic lives in newsscan.pipeline."""

from newsscan.config import get_settings
from newsscan.db import session_scope
from newsscan.ingest import ocr
from newsscan.pipeline import build_claim_services, run_scan
from newsscan.storage import LocalStorage
from newsscan.worker.celery_app import celery_app


@celery_app.task(name="newsscan.process_scan")
def process_scan(scan_id: str) -> None:
    settings = get_settings()
    extractor, lookup = build_claim_services(settings)  # (None, None) unless every key is set
    with session_scope() as session:
        run_scan(
            session,
            scan_id,
            storage=LocalStorage(settings.storage_dir),
            engine=ocr.get_ocr_engine(),  # looked up at call time so tests can replace it
            settings=settings,
            extractor=extractor,
            lookup=lookup,
        )
