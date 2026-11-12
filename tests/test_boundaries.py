"""Keeps the module boundaries from ADR-002 true. See CLAUDE.md for the rules."""

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "src" / "newsscan"

# Stage packages take data in and return data out. They must not know about HTTP, queues,
# the database or the pipeline that calls them.
STAGES = ["ingest", "extract", "analysis", "aggregate"]
FORBIDDEN = {"api", "worker", "db", "models", "pipeline", "storage", "main"}


def _imported_newsscan_modules(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "newsscan":
            parts = node.module.split(".")
            if len(parts) > 1:
                found.add(parts[1])
            else:  # `from newsscan import models`
                found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "newsscan" and len(parts) > 1:
                    found.add(parts[1])
    return found


def test_stage_packages_do_not_import_infrastructure():
    problems = []
    for stage in STAGES:
        for path in (PKG / stage).rglob("*.py"):
            bad = _imported_newsscan_modules(path) & FORBIDDEN
            if bad:
                problems.append(f"{path.relative_to(PKG)} imports {sorted(bad)}")
    assert not problems, "\n".join(problems)


def test_analysis_and_extract_depend_on_nothing_else_in_the_app():
    for stage in ("analysis", "extract"):
        for path in (PKG / stage).rglob("*.py"):
            assert _imported_newsscan_modules(path) <= {stage}, path


def test_api_only_uses_ingest_for_cheap_upload_validation():
    # The API talks to the database and the queue. Running the stages is the pipeline's job.
    for path in (PKG / "api").rglob("*.py"):
        used = _imported_newsscan_modules(path) & {"ingest", "extract", "analysis", "aggregate"}
        assert used <= {"ingest"}, f"{path.name} imports {sorted(used)}"
