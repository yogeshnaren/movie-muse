"""Other modules may import movie_muse.sync.api only."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.toolchain.boundaries import scan_file
from movie_muse.toolchain.paths import repo_root


@pytest.mark.architecture
def test_host_importing_sync_api_is_allowed(tmp_path: Path) -> None:
    src = tmp_path / "backend" / "app" / "sync_routes.py"
    src.parent.mkdir(parents=True)
    src.write_text("from movie_muse.sync.api import SyncProtocol\n", encoding="utf-8")
    assert scan_file(tmp_path, src) == []


@pytest.mark.architecture
def test_host_importing_sync_internal_module_is_rejected(tmp_path: Path) -> None:
    src = tmp_path / "backend" / "app" / "sync_routes.py"
    src.parent.mkdir(parents=True)
    src.write_text("from movie_muse.sync.protocol import SyncProtocol\n", encoding="utf-8")
    violations = scan_file(tmp_path, src)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_sync_module_does_not_import_persistence_internals() -> None:
    root = repo_root()
    package = root / "src" / "movie_muse" / "sync"
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "movie_muse.persistence.store" not in text
        assert "from movie_muse.persistence." not in text.replace(
            "from movie_muse.persistence.api import", ""
        )
