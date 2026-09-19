"""Hosts import movie_muse.platforms.api; internals are rejected."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.toolchain.boundaries import scan_file
from movie_muse.toolchain.paths import repo_root

HOSTS = (
    ("web", "open_web_app"),
    ("macos", "open_macos_app"),
    ("windows", "open_windows_app"),
    ("ios", "open_ios_app"),
    ("android", "open_android_app"),
)


@pytest.mark.architecture
def test_host_importing_platforms_api_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "apps" / "web" / "routes.py"
    source.parent.mkdir(parents=True)
    source.write_text("from movie_muse.platforms.api import open_platform\n", encoding="utf-8")
    assert scan_file(tmp_path, source) == []


@pytest.mark.architecture
def test_host_importing_platforms_internal_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "apps" / "web" / "routes.py"
    source.parent.mkdir(parents=True)
    source.write_text("from movie_muse.platforms.service import PlatformApp\n", encoding="utf-8")
    violations = scan_file(tmp_path, source)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_platforms_package_imports_only_public_sibling_apis() -> None:
    package = repo_root() / "src" / "movie_muse" / "platforms"
    siblings = (
        "artifacts",
        "audit",
        "authorization",
        "editor",
        "identity",
        "layout",
        "meeting_capture",
        "persistence",
        "project_memory",
        "revisions",
        "room_mode",
        "schemas",
        "sync",
    )
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for sibling in siblings:
            private_prefix = f"from movie_muse.{sibling}."
            public_import = f"from movie_muse.{sibling}.api import"
            assert private_prefix not in text.replace(public_import, "")
        assert "from tests." not in text


@pytest.mark.architecture
def test_platform_hosts_import_only_public_apis() -> None:
    root = repo_root()
    for folder, opener in HOSTS:
        host = root / "apps" / folder / "host.py"
        text = host.read_text(encoding="utf-8")
        assert "from movie_muse.platforms.api import" in text
        assert "from movie_muse.platforms.service" not in text
        assert opener in text
        assert "from tests." not in text
