"""Scan endpoints: upload a paper, then poll for the result."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from newsscan.api.schemas import ScanCreated, ScanOut
from newsscan.config import get_settings
from newsscan.db import get_session
from newsscan.ingest.loader import UnsupportedFileType, UploadRejected, validate_upload
from newsscan.models import Scan, ScanStatus, utcnow
from newsscan.observability import SCANS_FINISHED, SCANS_SUBMITTED
from newsscan.storage import LocalStorage
from newsscan.worker.tasks import process_scan

logger = logging.getLogger("newsscan.api")
router = APIRouter(prefix="/scans", tags=["scans"])


@router.post("", status_code=202, response_model=ScanCreated)
def create_scan(file: UploadFile, session: Session = Depends(get_session)) -> ScanCreated:
    """Accept a photo or scan of a paper (image or PDF) and queue it for processing."""
    settings = get_settings()

    data = file.file.read(settings.max_upload_bytes + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413, detail=f"The file is too large. The limit is {settings.max_upload_mb} MB."
        )
    try:
        kind = validate_upload(data, settings)
    except UnsupportedFileType as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except UploadRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    key = LocalStorage(settings.storage_dir).save(data)
    scan = Scan(
        input_kind=kind,
        content_type=(file.content_type or "")[:100],  # as declared by the client; untrusted
        size_bytes=len(data),
        storage_key=key,
    )
    session.add(scan)
    session.commit()  # commit before queueing, so the worker can always find the row

    try:
        process_scan.delay(scan.id)
    except Exception as exc:  # broker unreachable
        logger.exception("could not queue scan", extra={"scan_id": scan.id})
        scan.status = ScanStatus.FAILED.value
        scan.error = "The processing queue is unavailable. Try again shortly."
        scan.finished_at = utcnow()
        session.commit()
        SCANS_FINISHED.labels(outcome="failed").inc()
        raise HTTPException(status_code=503, detail=scan.error) from exc

    SCANS_SUBMITTED.inc()
    logger.info("scan queued", extra={"scan_id": scan.id, "input_kind": kind, "bytes": len(data)})
    return ScanCreated(id=scan.id, status=ScanStatus.QUEUED.value)


@router.get("/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: str, response: Response, session: Session = Depends(get_session)) -> ScanOut:
    try:
        uuid.UUID(scan_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Scan not found.") from None
    scan = session.get(Scan, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found.")
    response.headers["Cache-Control"] = "no-store"  # scans contain user documents
    return ScanOut.model_validate(scan)
