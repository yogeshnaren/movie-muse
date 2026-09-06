"""Backend/frontend hosts and other modules may only import ``movie_muse.schemas.api``.

MM-002 acceptance criterion 6 and 10. Reuses the shared boundary scanner
(``movie_muse.toolchain.boundaries``, MM-001) as a read-only utility; this
test does not modify that module or its own test suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.toolchain.boundaries import scan_boundaries, scan_file
from movie_muse.toolchain.paths import repo_root


@pytest.mark.architecture
def test_backend_importing_schemas_public_api_is_allowed(tmp_path: Path) -> None:
    src = tmp_path / "backend" / "app" / "screenplay_routes.py"
    src.parent.mkdir(parents=True)
    src.write_text("from movie_muse.schemas.api import Project, ScreenplayDocument\n", encoding="utf-8")
    assert scan_file(tmp_path, src) == []


@pytest.mark.architecture
def test_backend_importing_schemas_internal_module_is_rejected(tmp_path: Path) -> None:
    src = tmp_path / "backend" / "app" / "screenplay_routes.py"
    src.parent.mkdir(parents=True)
    src.write_text("from movie_muse.schemas.document import Block\n", encoding="utf-8")
    violations = scan_file(tmp_path, src)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_other_module_importing_schemas_internal_module_is_rejected(tmp_path: Path) -> None:
    src = tmp_path / "src" / "movie_muse" / "document" / "api.py"
    src.parent.mkdir(parents=True)
    src.write_text("from movie_muse.schemas.epistemic import AuthoredFact\n", encoding="utf-8")
    violations = scan_file(tmp_path, src)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_other_module_importing_schemas_api_is_allowed(tmp_path: Path) -> None:
    src = tmp_path / "src" / "movie_muse" / "document" / "api.py"
    src.parent.mkdir(parents=True)
    src.write_text("from movie_muse.schemas.api import ScreenplayDocument\n", encoding="utf-8")
    assert scan_file(tmp_path, src) == []


@pytest.mark.architecture
def test_repository_has_no_schemas_boundary_violations() -> None:
    assert scan_boundaries(repo_root()) == []
