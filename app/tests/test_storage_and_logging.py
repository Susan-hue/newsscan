import json
import logging

import pytest

from newsscan.observability import JsonFormatter
from newsscan.storage import LocalStorage


def test_storage_round_trip_uses_a_random_key(tmp_path):
    storage = LocalStorage(tmp_path)
    key = storage.save(b"hello")
    assert len(key) == 32 and storage.read(key) == b"hello"
    storage.delete(key)
    with pytest.raises(FileNotFoundError):
        storage.read(key)


@pytest.mark.parametrize("key", ["../../etc/passwd", "a" * 31, "G" * 32, "", "/abs/path"])
def test_storage_rejects_keys_that_are_not_plain_hex(tmp_path, key):
    with pytest.raises(ValueError):
        LocalStorage(tmp_path).read(key)


def test_json_logs_carry_extra_fields():
    record = logging.LogRecord("newsscan.pipeline", logging.INFO, __file__, 1, "stage finished", (), None)
    record.scan_id = "abc"
    record.stage = "ocr"
    payload = json.loads(JsonFormatter().format(record))
    assert payload["msg"] == "stage finished"
    assert payload["scan_id"] == "abc" and payload["stage"] == "ocr"
    assert payload["level"] == "INFO" and "ts" in payload
