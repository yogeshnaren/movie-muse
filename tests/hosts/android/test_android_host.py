"""Android host uses app-private files with MODE_PRIVATE."""

from __future__ import annotations

from pathlib import Path

from apps.android.host import open_android_app, resume_android_app

from movie_muse.platforms.api import GOLDEN_PROJECT_ID, ProtectionClass


def test_android_host_opens_and_resumes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    app = open_android_app(home)
    assert app.identity_snapshot().project_id == GOLDEN_PROJECT_ID
    assert app.storage.protection is ProtectionClass.MODE_PRIVATE
    assert "com.moviemuse.app" in app.storage.root
    app.light_edit("Android saved locally.")
    app.close()
    resumed = resume_android_app(home)
    assert "Android saved locally." in resumed.editor.document().blocks[1].text
    resumed.close()
