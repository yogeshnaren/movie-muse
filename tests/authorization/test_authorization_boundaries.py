"""Other modules may import movie_muse.authorization.api only."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.toolchain.boundaries import scan_file
from movie_muse.toolchain.paths import repo_root


@pytest.mark.architecture
def test_host_importing_authorization_api_is_allowed(tmp_path: Path) -> None:
    src = tmp_path / "backend" / "app" / "acl_routes.py"
    src.parent.mkdir(parents=True)
    src.write_text(
        "from movie_muse.authorization.api import AuthorizationService, authorize\n",
        encoding="utf-8",
    )
    assert scan_file(tmp_path, src) == []


@pytest.mark.architecture
def test_host_importing_authorization_internal_module_is_rejected(tmp_path: Path) -> None:
    src = tmp_path / "backend" / "app" / "acl_routes.py"
    src.parent.mkdir(parents=True)
    src.write_text("from movie_muse.authorization.policy import ROLE_ACTIONS\n", encoding="utf-8")
    violations = scan_file(tmp_path, src)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_repository_authorization_package_uses_only_public_sibling_apis() -> None:
    root = repo_root()
    package = root / "src" / "movie_muse" / "authorization"
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "from movie_muse.identity." not in text.replace("from movie_muse.identity.api import", "")
        assert "from movie_muse.audit." not in text.replace("from movie_muse.audit.api import", "")
        assert "from movie_muse.revisions." not in text.replace("from movie_muse.revisions.api import", "")
        assert "from movie_muse.persistence." not in text.replace(
            "from movie_muse.persistence.api import", ""
        )
        assert "from movie_muse.schemas." not in text.replace("from movie_muse.schemas.api import", "")
