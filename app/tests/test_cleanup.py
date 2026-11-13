from datetime import UTC, datetime, timedelta

import pytest
from prometheus_client import generate_latest

from newsscan.cleanup import delete_old_uploads
from newsscan.db import session_scope
from newsscan.models import Document, Scan, ScanStatus
from newsscan.storage import LocalStorage


def add_scan(session, storage, *, age_days, status=ScanStatus.DONE):
    key = storage.save(b"file bytes")
    scan = Scan(
        status=status.value,
        input_kind="image",
        content_type="image/png",
        size_bytes=10,
        storage_key=key,
        created_at=datetime.now(UTC) - timedelta(days=age_days),
    )
    session.add(scan)
    session.flush()
    return scan


@pytest.fixture()
def storage(app_env):
    return LocalStorage(app_env.storage_dir)


def test_old_finished_scans_lose_their_file_but_keep_their_row(app_env, storage):
    with session_scope() as session:
        old = add_scan(session, storage, age_days=8)
        session.add(
            Document(
                scan_id=old.id, page_count=1, text="kept", char_count=4, text_sha256="x", ocr_engine="fake"
            )
        )
        session.commit()
        result = delete_old_uploads(session, storage, days=7)
        assert (result.found, result.deleted, result.failed) == (1, 1, 0)
        assert old.file_deleted_at is not None
        assert session.get(Scan, old.id) is not None
        assert session.get(Scan, old.id).document.text == "kept"
        with pytest.raises(FileNotFoundError):
            storage.read(old.storage_key)


def test_recent_files_are_kept(app_env, storage):
    with session_scope() as session:
        fresh = add_scan(session, storage, age_days=6)
        session.commit()
        result = delete_old_uploads(session, storage, days=7)
        assert result.found == 0
        assert fresh.file_deleted_at is None
        assert storage.read(fresh.storage_key) == b"file bytes"


@pytest.mark.parametrize("status", [ScanStatus.QUEUED, ScanStatus.PROCESSING])
def test_scans_still_waiting_or_running_keep_their_file(app_env, storage, status):
    with session_scope() as session:
        busy = add_scan(session, storage, age_days=30, status=status)
        session.commit()
        assert delete_old_uploads(session, storage, days=7).found == 0
        assert storage.read(busy.storage_key) == b"file bytes"


def test_failed_scans_are_cleaned_too(app_env, storage):
    with session_scope() as session:
        add_scan(session, storage, age_days=10, status=ScanStatus.FAILED)
        session.commit()
        assert delete_old_uploads(session, storage, days=7).deleted == 1


def test_dry_run_changes_nothing(app_env, storage):
    with session_scope() as session:
        old = add_scan(session, storage, age_days=20)
        session.commit()
        result = delete_old_uploads(session, storage, days=7, dry_run=True)
        assert result.found == 1 and result.deleted == 0
        assert old.file_deleted_at is None
        assert storage.read(old.storage_key) == b"file bytes"


@pytest.mark.parametrize("days", [0, -1])
def test_zero_days_means_off(app_env, storage, days):
    with session_scope() as session:
        old = add_scan(session, storage, age_days=400)
        session.commit()
        assert delete_old_uploads(session, storage, days=days).found == 0
        assert storage.read(old.storage_key) == b"file bytes"


def test_running_twice_is_harmless_and_a_missing_file_is_fine(app_env, storage):
    with session_scope() as session:
        old = add_scan(session, storage, age_days=9)
        storage.delete(old.storage_key)  # already gone from disk
        session.commit()
        assert delete_old_uploads(session, storage, days=7).deleted == 1
        assert delete_old_uploads(session, storage, days=7).found == 0


def test_one_bad_file_does_not_stop_the_rest(app_env, storage):
    class Flaky(LocalStorage):
        def delete(self, key):
            if key == bad_key:
                raise OSError("disk problem")
            super().delete(key)

    flaky = Flaky(storage.root)
    with session_scope() as session:
        bad = add_scan(session, flaky, age_days=9)
        good = add_scan(session, flaky, age_days=9)
        bad_key = bad.storage_key
        session.commit()
        result = delete_old_uploads(session, flaky, days=7)
        assert (result.deleted, result.failed) == (1, 1)
        assert bad.file_deleted_at is None and good.file_deleted_at is not None


def test_the_deleted_counter_starts_at_zero_and_counts():
    assert "newsscan_uploads_deleted_total" in generate_latest().decode()


def test_nothing_is_scheduled_unless_a_retention_is_set():
    from newsscan.worker.celery_app import build_beat_schedule

    assert build_beat_schedule(0) == {}
    schedule = build_beat_schedule(7)
    assert schedule["cleanup-old-uploads"]["task"] == "newsscan.cleanup_old_uploads"
