"""Hosts import movie_muse.video_previs.api; internals are rejected."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from movie_muse.toolchain.boundaries import scan_file
from movie_muse.toolchain.paths import repo_root


@pytest.mark.architecture
def test_host_importing_video_previs_api_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "video_previs_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.video_previs.api import VideoPrevisService\n",
        encoding="utf-8",
    )
    assert scan_file(tmp_path, source) == []


@pytest.mark.architecture
def test_host_importing_video_previs_internal_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "video_previs_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.video_previs.service import VideoPrevisService\n",
        encoding="utf-8",
    )
    violations = scan_file(tmp_path, source)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_video_previs_package_imports_only_public_sibling_apis() -> None:
    package = repo_root() / "src" / "movie_muse" / "video_previs"
    siblings = (
        "artifacts",
        "audit",
        "authorization",
        "identity",
        "jobs",
        "model_router",
        "persistence",
        "revisions",
        "schemas",
        "shot_ir",
        "storyboard",
    )
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for sibling in siblings:
            private_prefix = f"from movie_muse.{sibling}."
            public_import = f"from movie_muse.{sibling}.api import"
            assert private_prefix not in text.replace(public_import, "")
        assert "from movie_muse.proposals" not in text
        assert "from tests." not in text
        assert "ChangeSet" not in text


def test_ext_video_provider_gate_stays_not_run() -> None:
    """EXT-VIDEO-PROVIDER remains NOT_RUN. Contract tests are not live smoke."""

    manifest = yaml.safe_load(
        (repo_root() / "movie_muse_build_status.yaml").read_text(encoding="utf-8")
    )
    gates = {item["id"]: item for item in manifest["external_gates"]}
    gate = gates["EXT-VIDEO-PROVIDER"]
    assert gate["owner_item"] == "MM-034"
    assert gate["status"] == "NOT_RUN"
    assert gate["evidence"] == []
