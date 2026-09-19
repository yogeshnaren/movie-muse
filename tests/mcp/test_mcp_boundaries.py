"""Hosts import movie_muse.mcp.api; internals are rejected."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.toolchain.boundaries import scan_file
from movie_muse.toolchain.paths import repo_root


@pytest.mark.architecture
def test_host_importing_mcp_api_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "mcp_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text("from movie_muse.mcp.api import MeshMcpService\n", encoding="utf-8")
    assert scan_file(tmp_path, source) == []


@pytest.mark.architecture
def test_host_importing_mcp_internal_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "mcp_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text("from movie_muse.mcp.service import MeshMcpService\n", encoding="utf-8")
    violations = scan_file(tmp_path, source)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_mcp_package_imports_only_public_sibling_apis() -> None:
    package = repo_root() / "src" / "movie_muse" / "mcp"
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "from movie_muse.api.service import" not in text
        assert "from tests." not in text
