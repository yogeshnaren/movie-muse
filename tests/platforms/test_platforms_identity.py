"""Golden project identity, parity, offline recover, and live workspaces."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.platforms.api import (
    GOLDEN_DOCUMENT_ID,
    GOLDEN_PROJECT_ID,
    MIN_TOUCH_TARGET_PT,
    PARITY_AS_OF,
    CaptureConsentError,
    LongFormUnavailableError,
    PlatformId,
    ProtectionClass,
    SyncUploadBlockedError,
    open_platform,
    parity_matrix,
    resume_platform,
)


def test_all_platforms_open_the_same_golden_identity(tmp_path: Path) -> None:
    snapshots = []
    for platform in PlatformId:
        app = open_platform(platform, tmp_path / platform.value)
        snap = app.identity_snapshot()
        assert snap.project_id == GOLDEN_PROJECT_ID
        assert snap.document_id == GOLDEN_DOCUMENT_ID
        assert (Path(app.storage.root) / "movie_muse.sqlite").is_file()
        snapshots.append(snap)
        app.close()
    layout_hashes = {item.layout_hash for item in snapshots}
    revisions = {item.revision_id for item in snapshots}
    assert len(layout_hashes) == 1
    assert len(revisions) == 1
    assert snapshots[0].layout_engine_version


def test_parity_matrix_is_dated_and_splits_jobs() -> None:
    rows = {row.platform: row for row in parity_matrix()}
    assert all(row.as_of == PARITY_AS_OF for row in rows.values())
    assert rows[PlatformId.WEB].long_form is True
    assert rows[PlatformId.MACOS].focus.value == "professional_authoring"
    assert rows[PlatformId.IOS].long_form is False
    assert rows[PlatformId.ANDROID].capture is True
    assert rows[PlatformId.IOS].room is True


def test_offline_edit_recovers_and_outage_blocks_upload(tmp_path: Path) -> None:
    home = tmp_path / "macos-home"
    app = open_platform(PlatformId.MACOS, home)
    app.light_edit("Ada waits at video village.")
    app.set_outage("auth_outage", True)
    app.light_edit("Ada waits through an auth outage.")
    with pytest.raises(SyncUploadBlockedError):
        app.flush_sync()
    link = app.deep_link()
    parsed = app.parse_deep_link(link)
    assert parsed.project_id == GOLDEN_PROJECT_ID
    app.close()
    resumed = resume_platform(PlatformId.MACOS, home)
    assert "auth outage" in resumed.editor.document().blocks[1].text
    assert resumed.identity_snapshot().document_id == GOLDEN_DOCUMENT_ID
    resumed.close()


def test_mobile_refuses_long_form_and_requires_capture_consent(tmp_path: Path) -> None:
    app = open_platform(PlatformId.IOS, tmp_path / "ios")
    with pytest.raises(LongFormUnavailableError):
        app.long_form_checkpoint("draft")
    meeting_id = app.begin_capture()
    assert meeting_id.startswith("mtg_")
    desktop = open_platform(PlatformId.WEB, tmp_path / "web-no-capture")
    with pytest.raises(CaptureConsentError):
        desktop.begin_capture()
    desktop.close()
    assert app.grant_capture_consent() == "granted"
    card_id = app.add_board_card("hold the wide")
    assert card_id
    assert app.cards()
    assert any("call sheet" in item for item in app.references())
    assert MIN_TOUCH_TARGET_PT <= app.accessibility().min_touch_target_pt
    note = app.annotate("mark the playback")
    assert note.within_budget
    assert note.target_pt >= MIN_TOUCH_TARGET_PT
    assert app.limitations()
    app.close()


def test_web_origin_isolation(tmp_path: Path) -> None:
    home = tmp_path / "web-home"
    a = open_platform(PlatformId.WEB, home, origin="https://app.moviemuse.local")
    b = open_platform(PlatformId.WEB, home, origin="https://other.example")
    assert Path(a.storage.root) != Path(b.storage.root)
    assert a.storage.protection is ProtectionClass.ORIGIN_ISOLATED
    a.light_edit("Ada stays on origin A.")
    assert "origin A" not in b.editor.document().blocks[1].text
    a.close()
    b.close()


def test_reconnect_flushes_outbox_after_outage(tmp_path: Path) -> None:
    app = open_platform(PlatformId.WEB, tmp_path / "web-reconnect")
    app.set_outage("sync_outage", True)
    app.light_edit("Ada waits through a sync outage.")
    blocked = app.reconnect()
    assert blocked["flushed"] == ()
    app.set_outage("sync_outage", False)
    recovered = app.reconnect()
    assert recovered["flushed"]
    assert recovered["last_synced"] in recovered["flushed"]
    app.close()


def test_desktop_allows_long_form(tmp_path: Path) -> None:
    app = open_platform(PlatformId.WINDOWS, tmp_path / "win")
    marker = app.long_form_checkpoint("white")
    assert marker
    assert app.storage.protection is ProtectionClass.LOCALAPPDATA_RESTRICTED
    app.close()
