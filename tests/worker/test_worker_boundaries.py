"""Public API and sibling-import contracts for the worker module."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.toolchain.boundaries import scan_file
from movie_muse.toolchain.paths import repo_root


@pytest.mark.architecture
def test_host_importing_worker_api_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "worker_host.py"
    source.parent.mkdir(parents=True)
    source.write_text("from movie_muse.worker.api import WorkerRuntime\n", encoding="utf-8")
    assert scan_file(tmp_path, source) == []


@pytest.mark.architecture
def test_host_importing_worker_internal_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "worker_host.py"
    source.parent.mkdir(parents=True)
    source.write_text("from movie_muse.worker.runtime import WorkerRuntime\n", encoding="utf-8")
    violations = scan_file(tmp_path, source)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_worker_package_imports_only_public_sibling_apis() -> None:
    package = repo_root() / "src" / "movie_muse" / "worker"
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "from movie_muse.jobs." not in text.replace(
            "from movie_muse.jobs.api import", ""
        )
        assert "from movie_muse.jobs.service" not in text
        assert "from movie_muse.jobs.storage" not in text
