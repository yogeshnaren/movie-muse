"""macOS host uses Application Support with restricted mode."""

from __future__ import annotations

from pathlib import Path

from apps.macos.host import open_macos_app, resume_macos_app
from movie_muse.platforms.api import GOLDEN_PROJECT_ID, ProtectionClass


def test_macos_host_opens_and_resumes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    app = open_macos_app(home)
    assert app.identity_snapshot().project_id == GOLDEN_PROJECT_ID
    assert app.storage.protection is ProtectionClass.APPLICATION_SUPPORT_0700
    assert "Application Support" in app.storage.root
    assert Path(app.storage.root).stat().st_mode & 0o777 == 0o700
    app.light_edit("macOS saved locally.")
    app.close()
    resumed = resume_macos_app(home)
    assert "macOS saved locally." in resumed.editor.document().blocks[1].text
    resumed.close()
