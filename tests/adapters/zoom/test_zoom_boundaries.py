"""Hosts import movie_muse.adapters.zoom.api; internals are rejected."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from movie_muse.toolchain.boundaries import scan_file
from movie_muse.toolchain.paths import repo_root


@pytest.mark.architecture
def test_host_importing_zoom_api_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "zoom_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.adapters.zoom.api import ZoomAdapter\n",
        encoding="utf-8",
    )
    assert scan_file(tmp_path, source) == []


@pytest.mark.architecture
def test_host_importing_zoom_internal_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "zoom_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.adapters.zoom.service import ZoomAdapter\n",
        encoding="utf-8",
    )
    violations = scan_file(tmp_path, source)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_zoom_package_imports_only_public_sibling_apis() -> None:
    package = repo_root() / "src" / "movie_muse" / "adapters" / "zoom"
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
        assert "from movie_muse.adapters.google_meet" not in text
        assert "from movie_muse.model_router" not in text
        assert "from tests." not in text


def test_ext_zoom_sandbox_gate_stays_not_run() -> None:
    """EXT-ZOOM-SANDBOX remains NOT_RUN. Contract tests are not live OAuth."""

    manifest = yaml.safe_load(
        (repo_root() / "movie_muse_build_status.yaml").read_text(encoding="utf-8")
    )
    gates = {item["id"]: item for item in manifest["external_gates"]}
    gate = gates["EXT-ZOOM-SANDBOX"]
    assert gate["owner_item"] == "MM-029"
    assert gate["status"] == "NOT_RUN"
    assert gate["evidence"] == []
