"""Delete old uploaded files. The database rows stay (ADR-014).

Only finished scans (done or failed) are touched. A scan still waiting or running keeps its file.
Run by hand to see what would happen:

    python -m newsscan.cleanup --days 7 --dry-run
"""

import argparse
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from newsscan.models import Scan, ScanStatus
from newsscan.observability import UPLOADS_DELETED
from newsscan.storage import LocalStorage

logger = logging.getLogger("newsscan.cleanup")


@dataclass
class CleanupResult:
    found: int = 0
    deleted: int = 0
    failed: int = 0


def delete_old_uploads(
    session: Session,
    storage: LocalStorage,
    days: int,
    *,
    dry_run: bool = False,
    now: datetime | None = None,
) -> CleanupResult:
    """Remove files of finished scans older than `days`. With days <= 0 nothing is touched."""
    result = CleanupResult()
    if days <= 0:
        return result
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
    rows = session.scalars(
        select(Scan).where(
            Scan.created_at < cutoff,
            Scan.file_deleted_at.is_(None),
            Scan.status.in_([ScanStatus.DONE.value, ScanStatus.FAILED.value]),
        )
    ).all()
    result.found = len(rows)
    if dry_run:
        return result
    for scan in rows:
        try:
            storage.delete(scan.storage_key)  # a file that is already gone is fine
            scan.file_deleted_at = datetime.now(UTC)
            session.commit()  # one row at a time, so a crash never loses track of what is deleted
        except Exception:
            session.rollback()
            result.failed += 1
            logger.exception("could not delete upload", extra={"scan_id": scan.id})
            continue
        result.deleted += 1
        UPLOADS_DELETED.inc()
    logger.info(
        "upload cleanup finished",
        extra={"found": result.found, "deleted": result.deleted, "failed": result.failed, "days": days},
    )
    return result


def main() -> None:
    from newsscan.config import get_settings
    from newsscan.db import session_scope

    parser = argparse.ArgumentParser(description="Delete uploaded files older than N days.")
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true", help="only count, delete nothing")
    args = parser.parse_args()
    settings = get_settings()
    with session_scope() as session:
        result = delete_old_uploads(
            session, LocalStorage(settings.storage_dir), args.days, dry_run=args.dry_run
        )
    if args.dry_run:
        print(f"dry run: {result.found} file(s) would be deleted")
    else:
        print(f"deleted {result.deleted} of {result.found} file(s); failed: {result.failed}")


if __name__ == "__main__":
    main()
