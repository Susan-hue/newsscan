import re
from pathlib import Path

from prometheus_client import generate_latest

from newsscan.observability import STAGES

# A counter that only appears at its first event makes rate() and increase() miss that event.
# So every known label combination must exist at 0 from the start.


def metrics_text() -> str:
    return generate_latest().decode()


def test_scan_outcomes_exist_from_the_start():
    text = metrics_text()
    for outcome in ("done", "failed"):
        assert f'newsscan_scans_finished_total{{outcome="{outcome}"}}' in text


def test_outside_calls_exist_from_the_start():
    text = metrics_text()
    for service in ("groq", "factcheck"):
        for outcome in ("ok", "error"):
            assert f'newsscan_external_calls_total{{outcome="{outcome}",service="{service}"}}' in text


def test_every_stage_timer_exists_from_the_start():
    text = metrics_text()
    for stage in STAGES:
        assert f'newsscan_stage_duration_seconds_count{{stage="{stage}"}}' in text


def test_the_stage_list_matches_the_pipeline():
    source = (Path(__file__).parents[1] / "src" / "newsscan" / "pipeline.py").read_text()
    used = set(re.findall(r'timed_stage\(logger, scan_id, "([a-z_]+)"\)', source))
    assert used == set(STAGES), (
        "a stage was added or renamed in pipeline.py: update STAGES in observability.py"
    )
