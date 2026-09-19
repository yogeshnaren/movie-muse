from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.toolchain.boundaries import scan_file
from movie_muse.toolchain.paths import repo_root
from movie_muse.toolchain.yamlio import load_mapping


@pytest.mark.architecture
def test_module_layout_declares_monolith_and_mm001_toolchain() -> None:
    root = repo_root()
    layout = load_mapping(root / "config" / "module-layout.yaml")
    assert layout["architecture"] == "modular_monolith_plus_durable_worker"
    modules = {entry["id"]: entry for entry in layout["modules"]}
    assert modules["toolchain"]["owner_item"] == "MM-001"
    assert modules["document"]["public"] == "movie_muse.document.api"


@pytest.mark.architecture
def test_public_api_import_is_allowed(tmp_path: Path) -> None:
    src = tmp_path / "src" / "movie_muse" / "document" / "api.py"
    src.parent.mkdir(parents=True)
    src.write_text("from movie_muse.revisions.api import Merge\n", encoding="utf-8")
    assert scan_file(tmp_path, src) == []


@pytest.mark.architecture
def test_cross_module_internal_import_is_rejected(tmp_path: Path) -> None:
    src = tmp_path / "src" / "movie_muse" / "document" / "api.py"
    src.parent.mkdir(parents=True)
    src.write_text("from movie_muse.revisions.internal import tables\n", encoding="utf-8")
    violations = scan_file(tmp_path, src)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_same_module_internal_import_is_allowed(tmp_path: Path) -> None:
    src = tmp_path / "src" / "movie_muse" / "document" / "api.py"
    src.parent.mkdir(parents=True)
    src.write_text("from movie_muse.document.internal import normalize\n", encoding="utf-8")
    assert scan_file(tmp_path, src) == []


@pytest.mark.architecture
def test_application_host_internal_import_is_rejected(tmp_path: Path) -> None:
    src = tmp_path / "backend" / "app" / "main.py"
    src.parent.mkdir(parents=True)
    src.write_text("from movie_muse.revisions.internal import tables\n", encoding="utf-8")
    violations = scan_file(tmp_path, src)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_scan_roots_include_backend_host() -> None:
    from movie_muse.toolchain.boundaries import iter_python_files

    files = iter_python_files(repo_root(), ["backend/app"])
    assert any(path.name == "main.py" for path in files)


@pytest.mark.architecture
def test_repository_has_no_boundary_violations() -> None:
    from movie_muse.toolchain.boundaries import scan_boundaries

    assert scan_boundaries(repo_root()) == []
