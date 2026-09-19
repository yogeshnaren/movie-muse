"""iOS host uses sandboxed Documents with complete protection."""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.ios.host import open_ios_app, resume_ios_app
from movie_muse.platforms.api import GOLDEN_PROJECT_ID, LongFormUnavailableError, ProtectionClass


def test_ios_host_opens_and_resumes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    app = open_ios_app(home)
    assert app.identity_snapshot().project_id == GOLDEN_PROJECT_ID
    assert app.storage.protection is ProtectionClass.NSFILEPROTECTION_COMPLETE
    assert "Documents" in app.storage.root
    with pytest.raises(LongFormUnavailableError):
        app.long_form_checkpoint("not on phone")
    app.annotate("slate mark")
    app.close()
    resumed = resume_ios_app(home)
    assert any("slate mark" in note.text for note in resumed.editor.document().notes)
    resumed.close()
