"""Android host imports the public platforms API only."""

from __future__ import annotations

from movie_muse.toolchain.paths import repo_root


def test_android_host_imports_public_api() -> None:
    text = (repo_root() / "apps" / "android" / "host.py").read_text(encoding="utf-8")
    assert "from movie_muse.platforms.api import" in text
    assert "from movie_muse.platforms.service" not in text
    assert "from tests." not in text
