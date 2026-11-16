"""Write per-container CPU, memory, network and disk numbers for Node Exporter to pick up.

Why this exists: cAdvisor can't name containers on this Docker (ADR-016), but `docker stats` can.
It runs on the computer, not in a container, so nothing needs the Docker socket.

    python3 scripts/docker_stats.py            # writes textfile/docker_containers.prom
    python3 scripts/docker_stats.py --print    # shows the numbers instead

Node Exporter reads every .prom file in textfile/ and shows it to Prometheus.
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "textfile" / "docker_containers.prom"

# Docker prints memory in binary units (MiB) and network and disk in decimal units (MB).
_UNITS = {
    "B": 1,
    "kB": 1000,
    "KB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
    "TB": 1000**4,
    "KiB": 1024,
    "MiB": 1024**2,
    "GiB": 1024**3,
    "TiB": 1024**4,
}
_AMOUNT = re.compile(r"^\s*([0-9.]+)\s*([A-Za-z]+)\s*$")

# (metric name, help text, which Docker field and part)
METRICS = [
    ("cpu_percent", "CPU used, in percent of one core (can pass 100)"),
    ("memory_usage_bytes", "Memory in use"),
    ("memory_limit_bytes", "Memory the container may use"),
    ("network_receive_bytes", "Bytes received since the container started"),
    ("network_transmit_bytes", "Bytes sent since the container started"),
    ("block_read_bytes", "Bytes read from disk since the container started"),
    ("block_write_bytes", "Bytes written to disk since the container started"),
    ("pids", "Processes inside the container"),
]


def to_bytes(text: str) -> float:
    """'8.492MiB' -> 8904187.9. Raises ValueError on anything it doesn't understand."""
    match = _AMOUNT.match(text)
    if not match or match.group(2) not in _UNITS:
        raise ValueError(f"unreadable amount: {text!r}")
    return float(match.group(1)) * _UNITS[match.group(2)]


def _pair(text: str) -> tuple[float, float]:
    left, right = text.split("/")
    return to_bytes(left), to_bytes(right)


def parse_row(row: dict) -> tuple[str, dict[str, float]]:
    """One line of `docker stats --format json` -> (container name, numbers)."""
    memory_used, memory_limit = _pair(row["MemUsage"])
    received, sent = _pair(row["NetIO"])
    read, written = _pair(row["BlockIO"])
    values = {
        "cpu_percent": float(row["CPUPerc"].rstrip("%")),
        "memory_usage_bytes": memory_used,
        "memory_limit_bytes": memory_limit,
        "network_receive_bytes": received,
        "network_transmit_bytes": sent,
        "block_read_bytes": read,
        "block_write_bytes": written,
        "pids": float(row["PIDs"]),
    }
    return row["Name"], values


def render(rows: list[dict]) -> str:
    """Prometheus text format. A container with an unreadable row is skipped, the rest still count."""
    containers: list[tuple[str, dict[str, float]]] = []
    for row in rows:
        try:
            containers.append(parse_row(row))
        except (KeyError, ValueError):
            continue
    lines: list[str] = []
    for metric, help_text in METRICS:
        full = f"newsscan_docker_container_{metric}"
        lines += [f"# HELP {full} {help_text}", f"# TYPE {full} gauge"]
        for name, values in sorted(containers):
            lines.append(f'{full}{{name="{_label(name)}"}} {values[metric]:g}')
    return "\n".join(lines) + "\n"


def _label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def read_docker_stats() -> list[dict]:
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


def write_atomically(path: Path, text: str) -> None:
    """Write to a temporary file, then rename, so Node Exporter never reads half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, suffix=".tmp", delete=False) as handle:
        handle.write(text)
        temp = Path(handle.name)
    temp.chmod(0o644)  # the exporter runs as another user and must be able to read it
    temp.replace(path)


def main() -> int:
    try:
        text = render(read_docker_stats())
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError) as exc:
        print(f"docker stats failed: {exc}", file=sys.stderr)
        return 1  # the old file stays, and its age shows up in node_textfile_mtime_seconds
    if "--print" in sys.argv:
        print(text, end="")
    else:
        write_atomically(OUTPUT, text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
