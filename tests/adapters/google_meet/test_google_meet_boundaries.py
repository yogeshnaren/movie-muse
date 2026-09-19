"""Hosts import movie_muse.adapters.google_meet.api; internals are rejected."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from movie_muse.toolchain.boundaries import scan_file
from movie_muse.toolchain.paths import repo_root


@pytest.mark.architecture
def test_host_importing_meet_api_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "meet_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.adapters.google_meet.api import GoogleMeetAdapter\n",
        encoding="utf-8",
    )
    assert scan_file(tmp_path, source) == []


@pytest.mark.architecture
def test_host_importing_meet_internal_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "meet_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.adapters.google_meet.service import GoogleMeetAdapter\n",
        encoding="utf-8",
    )
    violations = scan_file(tmp_path, source)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_meet_package_imports_only_public_sibling_apis() -> None:
    package = repo_root() / "src" / "movie_muse" / "adapters" / "google_meet"
    siblings = (
        "audit",
        "authorization",
        "identity",
        "meeting_capture",
        "persistence",
        "schemas",
    )
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for sibling in siblings:
            private_prefix = f"from movie_muse.{sibling}."
            public_import = f"from movie_muse.{sibling}.api import"
            assert private_prefix not in text.replace(public_import, "")
        assert "from movie_muse.adapters.zoom" not in text
        assert "from movie_muse.model_router" not in text
        assert "from tests." not in text


def test_ext_google_meet_sandbox_gate_stays_not_run() -> None:
    """Contract tests are not live OAuth. Ledger stays NOT_RUN until genuine PASS."""

    manifest = yaml.safe_load(
        (repo_root() / "movie_muse_build_status.yaml").read_text(encoding="utf-8")
    )
    gates = {item["id"]: item for item in manifest["external_gates"]}
    gate = gates["EXT-GOOGLE-MEET-SANDBOX"]
    assert gate["owner_item"] == "MM-029"
    status = str(gate["status"])
    assert status in {"NOT_RUN", "PASS"}
    evidence = list(gate.get("evidence") or [])
    if status == "NOT_RUN":
        assert evidence == []
    else:
        assert evidence
