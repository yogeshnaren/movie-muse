"""The workflow matrix is dated, owned, and internally consistent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from movie_muse.toolchain.paths import repo_root

ALLOWED_RESULTS = frozenset({"supported", "gap", "external"})
ALLOWED_PROTOCOLS = frozenset({"automated", "manual", "documented"})
FORBIDDEN_CLAIMS = (
    "equivalent to",
    "feature parity with",
    "identical to final draft",
    "identical to celtx",
    "identical to arc studio",
)


def _matrix_path() -> Path:
    return repo_root() / "docs" / "competitive" / "workflow-matrix.yaml"


def _load_matrix() -> dict[str, Any]:
    loaded = yaml.safe_load(_matrix_path().read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("workflow-matrix.yaml must be a mapping")
    return loaded


def _rows() -> tuple[dict[str, Any], ...]:
    rows = _load_matrix().get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("workflow matrix must list rows")
    return tuple(row for row in rows if isinstance(row, dict))


def test_matrix_has_dated_owner_and_disclaimer() -> None:
    matrix = _load_matrix()
    assert matrix["dated"]
    assert matrix["owner_item"] == "MM-016"
    assert matrix["release_blocking"] is True
    disclaimer = str(matrix["disclaimer"]).lower()
    assert "equivalent" not in disclaimer
    assert "observable" in disclaimer


def test_every_row_has_observable_fields() -> None:
    seen: set[str] = set()
    for row in _rows():
        row_id = str(row["id"])
        assert row_id not in seen
        seen.add(row_id)
        assert row["benchmark"]
        assert row["task"]
        assert row["criteria"]
        assert row["fixture"]
        assert row["protocol"] in ALLOWED_PROTOCOLS
        assert row["owner_item"].startswith("MM-")
        assert row["result"] in ALLOWED_RESULTS
        if row["result"] == "supported":
            assert row["protocol"] == "automated"
            assert str(row["automation"]).startswith("tests/competitive/")
            assert row.get("awaiting") in (None, "")
        if row["result"] == "gap":
            assert str(row["awaiting"]).startswith("MM-")
            assert row.get("automation") in (None, "")
        if row["result"] == "external":
            assert str(row["external_gate"]).startswith("EXT-")
            assert row["protocol"] == "manual"


def test_docs_do_not_claim_product_equivalence() -> None:
    root = _matrix_path().parent
    for path in root.glob("*.md"):
        text = path.read_text(encoding="utf-8").lower()
        for phrase in FORBIDDEN_CLAIMS:
            assert phrase not in text, f"{path} contains {phrase!r}"


def test_supported_automation_targets_exist() -> None:
    repo = repo_root()
    for row in _rows():
        if row["result"] != "supported":
            continue
        node = str(row["automation"])
        path_text, _, func = node.partition("::")
        path = repo / path_text
        assert path.is_file(), path
        assert f"def {func}(" in path.read_text(encoding="utf-8")
