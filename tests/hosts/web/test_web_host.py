"""Web host opens a live origin-isolated workspace."""

from __future__ import annotations

from pathlib import Path

from apps.web.host import open_web_app, resume_web_app

from movie_muse.platforms.api import GOLDEN_PROJECT_ID, ProtectionClass


def test_web_host_opens_and_resumes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    app = open_web_app(home)
    assert app.identity_snapshot().project_id == GOLDEN_PROJECT_ID
    assert app.storage.protection is ProtectionClass.ORIGIN_ISOLATED
    app.light_edit("Web saved locally.")
    app.close()
    resumed = resume_web_app(home)
    assert "Web saved locally." in resumed.editor.document().blocks[1].text
    resumed.close()
