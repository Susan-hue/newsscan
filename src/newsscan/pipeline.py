"""The scan pipeline: load -> preprocess -> ocr -> normalise -> register -> analyse -> report.

This module holds no web or queue code. The worker calls run_scan(), and tests call it directly
with a fake OCR engine. Every stage is timed (metric plus log line) so the monitoring platform
can show where a scan spent its time.
"""

import logging
from itertools import count

from sqlalchemy.orm import Session

from newsscan.aggregate.report import build_report
from newsscan.analysis.factcheck import FactCheck, FactCheckError, FactCheckLookup, GoogleFactCheckLookup
from newsscan.analysis.signals import (
    Signal,
    claim_checks_from_lookups,
    claim_checks_not_run,
    compute_signals,
    plausibility_cue,
    plausibility_cue_not_run,
)
from newsscan.config import Settings
from newsscan.extract.claims import ClaimExtractionError, ClaimExtractor, GroqClaimExtractor
from newsscan.extract.groq import LLMError
from newsscan.extract.normalize import normalise_text, text_fingerprint
from newsscan.extract.plausibility import GroqPlausibilityAssessor, PlausibilityAssessor
from newsscan.ingest.loader import UploadRejected, load_pages
from newsscan.ingest.ocr import OCREngine, OCRFailed
from newsscan.ingest.preprocess import prepare_for_ocr
from newsscan.models import Document, Report, Scan, ScanStatus, utcnow
from newsscan.observability import EXTERNAL_CALLS, SCANS_FINISHED, timed_stage
from newsscan.storage import LocalStorage

logger = logging.getLogger("newsscan.pipeline")


def run_scan(
    session: Session,
    scan_id: str,
    *,
    storage: LocalStorage,
    engine: OCREngine,
    settings: Settings,
    extractor: ClaimExtractor | None = None,
    lookup: FactCheckLookup | None = None,
    assessor: PlausibilityAssessor | None = None,
) -> None:
    scan = session.get(Scan, scan_id)
    if scan is None:
        logger.warning("scan not found", extra={"scan_id": scan_id})
        return
    if scan.status in (ScanStatus.DONE, ScanStatus.FAILED):
        # A queue can deliver the same job twice. Finished scans are left alone.
        logger.info("scan already finished", extra={"scan_id": scan_id, "status": scan.status})
        return

    scan.status = ScanStatus.PROCESSING.value
    scan.started_at = utcnow()
    scan.error = None
    session.commit()
    logger.info("scan started", extra={"scan_id": scan_id, "input_kind": scan.input_kind})

    try:
        _process(
            session,
            scan,
            storage=storage,
            engine=engine,
            settings=settings,
            extractor=extractor,
            lookup=lookup,
            assessor=assessor,
        )
    except (UploadRejected, OCRFailed) as exc:
        _fail(session, scan_id, str(exc), reason=type(exc).__name__)
    except Exception:
        logger.exception("scan crashed", extra={"scan_id": scan_id})
        _fail(session, scan_id, "Something went wrong while processing the scan.", reason="internal")


def build_claim_services(
    settings: Settings,
) -> tuple[ClaimExtractor | None, FactCheckLookup | None, PlausibilityAssessor | None]:
    """The real Groq and Google clients, or Nones when any key or the model is missing.

    Off by default so the text of a scan is never sent to an outside service by accident.
    """
    if not settings.claim_checking_enabled:
        return None, None, None
    assert settings.groq_api_key and settings.fact_check_api_key  # for the type checker; enabled implies set
    return (
        GroqClaimExtractor(settings.groq_api_key.get_secret_value(), settings.groq_model),
        GoogleFactCheckLookup(settings.fact_check_api_key.get_secret_value()),
        GroqPlausibilityAssessor(settings.groq_api_key.get_secret_value(), settings.groq_model),
    )


def check_claims(
    scan_id: str,
    text: str,
    extractor: ClaimExtractor,
    lookup: FactCheckLookup,
    limit: int,
) -> Signal:
    """Extract claims, look each one up, and return the claim_checks signal.

    Nothing here may fail the scan: the report is still useful without claim checks, so every
    failure becomes a `not_run` signal with a safe message. Claim text is never logged, only counts.
    """
    try:
        claims = extractor.extract(text, limit)
        EXTERNAL_CALLS.labels(service="groq", outcome="ok").inc()
    except ClaimExtractionError as exc:
        EXTERNAL_CALLS.labels(service="groq", outcome="error").inc()
        logger.warning("claim extraction failed", extra={"scan_id": scan_id})
        return claim_checks_not_run(str(exc))
    except Exception:
        EXTERNAL_CALLS.labels(service="groq", outcome="error").inc()
        logger.exception("claim extraction crashed", extra={"scan_id": scan_id})
        return claim_checks_not_run("Claim extraction failed unexpectedly.")

    found: dict[str, list[FactCheck]] = {}
    failures = 0
    for claim in claims:
        try:
            found[claim] = lookup.search(claim)
            EXTERNAL_CALLS.labels(service="factcheck", outcome="ok").inc()
        except Exception as exc:  # FactCheckError is the expected one; nothing else may fail the scan either
            failures += 1
            EXTERNAL_CALLS.labels(service="factcheck", outcome="error").inc()
            if not isinstance(exc, FactCheckError):
                logger.exception("fact-check lookup crashed", extra={"scan_id": scan_id})
    logger.info(
        "claims checked",
        extra={
            "scan_id": scan_id,
            "claims": len(claims),
            "matches": sum(len(v) for v in found.values()),
            "failures": failures,
        },
    )
    return claim_checks_from_lookups(claims, found, failures)


def assess_plausibility(scan_id: str, text: str, assessor: PlausibilityAssessor) -> Signal:
    """Ask the AI for satire markers. A failure is a `not_run` signal, never a failed scan."""
    try:
        result = assessor.assess(text)
        EXTERNAL_CALLS.labels(service="groq", outcome="ok").inc()
    except LLMError as exc:
        EXTERNAL_CALLS.labels(service="groq", outcome="error").inc()
        logger.warning("plausibility check failed", extra={"scan_id": scan_id})
        return plausibility_cue_not_run(str(exc))
    except Exception:
        EXTERNAL_CALLS.labels(service="groq", outcome="error").inc()
        logger.exception("plausibility check crashed", extra={"scan_id": scan_id})
        return plausibility_cue_not_run("The plausibility check failed unexpectedly.")
    logger.info("plausibility checked", extra={"scan_id": scan_id, "level": result.level})
    return plausibility_cue(result.level, result.reasons)


def _process(
    session: Session,
    scan: Scan,
    *,
    storage: LocalStorage,
    engine: OCREngine,
    settings: Settings,
    extractor: ClaimExtractor | None,
    lookup: FactCheckLookup | None,
    assessor: PlausibilityAssessor | None,
) -> None:
    scan_id = scan.id

    with timed_stage(logger, scan_id, "read_file"):
        data = storage.read(scan.storage_key)

    page_texts: list[str] = []
    weighted: list[tuple[float, int]] = []  # (confidence, characters) per page
    pages = load_pages(data, scan.input_kind, settings)
    for number in count(1):
        with timed_stage(logger, scan_id, "load"):
            page = next(pages, None)
        if page is None:
            break
        with timed_stage(logger, scan_id, "preprocess"):
            prepared = prepare_for_ocr(page)
        with timed_stage(logger, scan_id, "ocr"):
            result = engine.recognize(prepared)
        page_texts.append(result.text)
        if result.mean_confidence is not None:
            weighted.append((result.mean_confidence, max(len(result.text), 1)))
        logger.info(
            "page recognised",
            extra={"scan_id": scan_id, "page": number, "chars": len(result.text)},
        )

    with timed_stage(logger, scan_id, "normalise"):
        text = normalise_text("\n\n".join(page_texts))

    total = sum(weight for _, weight in weighted)
    mean_confidence = round(sum(c * w for c, w in weighted) / total, 1) if total else None

    with timed_stage(logger, scan_id, "register"):
        session.add(
            Document(
                scan_id=scan_id,
                page_count=len(page_texts),
                text=text,
                char_count=len(text),
                text_sha256=text_fingerprint(text),
                ocr_engine=engine.name,
                mean_confidence=mean_confidence,
            )
        )
        session.flush()

    claim_signal = None
    if extractor is not None and lookup is not None and text.strip():
        with timed_stage(logger, scan_id, "claims"):
            claim_signal = check_claims(scan_id, text, extractor, lookup, settings.max_claims_per_scan)

    plausibility_signal = None
    if assessor is not None and text.strip():
        with timed_stage(logger, scan_id, "plausibility"):
            plausibility_signal = assess_plausibility(scan_id, text, assessor)

    with timed_stage(logger, scan_id, "analyse"):
        signals = compute_signals(text, mean_confidence, claim_signal, plausibility_signal)

    with timed_stage(logger, scan_id, "report"):
        report = build_report(signals, len(text), mean_confidence)
        session.add(
            Report(
                scan_id=scan_id,
                band=report.band,
                summary=report.summary,
                signals=report.signals,
                limitations=report.limitations,
                pipeline_version=settings.pipeline_version,
            )
        )

    scan.status = ScanStatus.DONE.value
    scan.finished_at = utcnow()
    session.commit()
    SCANS_FINISHED.labels(outcome="done").inc()
    logger.info("scan done", extra={"scan_id": scan_id, "chars": len(text), "pages": len(page_texts)})


def _fail(session: Session, scan_id: str, message: str, *, reason: str) -> None:
    session.rollback()  # discard half-written document and report rows
    scan = session.get(Scan, scan_id)
    if scan is None:
        return
    scan.status = ScanStatus.FAILED.value
    scan.error = message
    scan.finished_at = utcnow()
    session.commit()
    SCANS_FINISHED.labels(outcome="failed").inc()
    logger.warning("scan failed", extra={"scan_id": scan_id, "reason": reason})
