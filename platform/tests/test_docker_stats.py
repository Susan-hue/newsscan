import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "docker_stats", Path(__file__).parents[1] / "scripts" / "docker_stats.py"
)
docker_stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docker_stats)

ROW = {
    "Name": "newsscan-worker-1",
    "CPUPerc": "0.09%",
    "MemUsage": "90.18MiB / 18.83GiB",
    "NetIO": "632kB / 1.53MB",
    "BlockIO": "946kB / 41kB",
    "PIDs": "3",
}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0B", 0),
        ("41kB", 41_000),
        ("1.53MB", 1_530_000),
        ("90.18MiB", 90.18 * 1024**2),
        ("18.83GiB", 18.83 * 1024**3),
    ],
)
def test_amounts_use_the_right_unit_size(text, expected):
    assert docker_stats.to_bytes(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["", "12", "12 parsecs", "MiB"])
def test_unreadable_amounts_are_refused(text):
    with pytest.raises(ValueError):
        docker_stats.to_bytes(text)


def test_a_row_becomes_numbers():
    name, values = docker_stats.parse_row(ROW)
    assert name == "newsscan-worker-1"
    assert values["cpu_percent"] == pytest.approx(0.09)
    assert values["memory_usage_bytes"] == pytest.approx(90.18 * 1024**2)
    assert values["network_transmit_bytes"] == 1_530_000
    assert values["pids"] == 3


def test_output_is_prometheus_text_with_one_line_per_container():
    text = docker_stats.render([ROW, {**ROW, "Name": "newsscan-api-1"}])
    assert "# TYPE newsscan_docker_container_cpu_percent gauge" in text
    assert 'newsscan_docker_container_pids{name="newsscan-api-1"} 3' in text
    assert 'newsscan_docker_container_pids{name="newsscan-worker-1"} 3' in text
    assert text.endswith("\n")


def test_one_broken_row_does_not_lose_the_others():
    text = docker_stats.render([{**ROW, "MemUsage": "garbage"}, {**ROW, "Name": "good"}])
    assert 'name="good"' in text
    assert 'name="newsscan-worker-1"' not in text


def test_quotes_in_a_name_cannot_break_the_file():
    text = docker_stats.render([{**ROW, "Name": 'a"b'}])
    assert 'name="a\\"b"' in text


def test_the_file_is_replaced_in_one_step_and_readable_by_others(tmp_path):
    target = tmp_path / "out.prom"
    docker_stats.write_atomically(target, "old\n")
    docker_stats.write_atomically(target, "new\n")
    assert target.read_text() == "new\n"
    assert target.stat().st_mode & 0o044 == 0o044
    assert [p.name for p in tmp_path.iterdir()] == ["out.prom"]
