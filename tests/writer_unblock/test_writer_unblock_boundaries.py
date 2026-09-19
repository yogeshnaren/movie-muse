"""Hosts import movie_muse.writer_unblock.api; internals are rejected."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.toolchain.boundaries import scan_file
from movie_muse.toolchain.paths import repo_root


@pytest.mark.architecture
def test_host_importing_writer_unblock_api_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "unblock_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.writer_unblock.api import WriterUnblockService\n",
        encoding="utf-8",
    )
    assert scan_file(tmp_path, source) == []


@pytest.mark.architecture
def test_host_importing_writer_unblock_internal_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "unblock_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.writer_unblock.service import WriterUnblockService\n",
        encoding="utf-8",
    )
    violations = scan_file(tmp_path, source)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_writer_unblock_package_imports_only_public_sibling_apis() -> None:
    package = repo_root() / "src" / "movie_muse" / "writer_unblock"
    siblings = (
        "audit",
        "authorization",
        "creative_intent",
        "identity",
        "model_router",
        "persistence",
        "proposals",
        "revisions",
        "schemas",
    )
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for sibling in siblings:
            private_prefix = f"from movie_muse.{sibling}."
            public_import = f"from movie_muse.{sibling}.api import"
            assert private_prefix not in text.replace(public_import, "")
