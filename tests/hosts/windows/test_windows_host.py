"""Windows host uses LocalAppData restricted storage."""

from __future__ import annotations

from pathlib import Path

from apps.windows.host import open_windows_app, resume_windows_app

from movie_muse.platforms.api import GOLDEN_PROJECT_ID, ProtectionClass


def test_windows_host_opens_and_resumes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    app = open_windows_app(home)
    assert app.identity_snapshot().project_id == GOLDEN_PROJECT_ID
    assert app.storage.protection is ProtectionClass.LOCALAPPDATA_RESTRICTED
    assert "AppData" in app.storage.root
    app.light_edit("Windows saved locally.")
    app.close()
    resumed = resume_windows_app(home)
    assert "Windows saved locally." in resumed.editor.document().blocks[1].text
    resumed.close()
