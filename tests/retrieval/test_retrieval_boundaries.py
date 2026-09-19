"""Hosts import movie_muse.retrieval.api; internals are rejected."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.toolchain.boundaries import scan_file
from movie_muse.toolchain.paths import repo_root


@pytest.mark.architecture
def test_host_importing_retrieval_api_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "retrieval_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.retrieval.api import RetrievalService\n",
        encoding="utf-8",
    )
    assert scan_file(tmp_path, source) == []


@pytest.mark.architecture
def test_host_importing_retrieval_internal_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "retrieval_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.retrieval.service import RetrievalService\n",
        encoding="utf-8",
    )
    violations = scan_file(tmp_path, source)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_retrieval_package_imports_only_public_sibling_apis() -> None:
    package = repo_root() / "src" / "movie_muse" / "retrieval"
    siblings = (
        "audit",
        "authorization",
        "identity",
        "persistence",
        "rights",
        "schemas",
        "context",
        "model_router",
    )
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for sibling in siblings:
            private_prefix = f"from movie_muse.{sibling}."
            public_import = f"from movie_muse.{sibling}.api import"
            assert private_prefix not in text.replace(public_import, "")
        assert "from movie_muse.model_router" not in text
        assert "import movie_muse.model_router" not in text
