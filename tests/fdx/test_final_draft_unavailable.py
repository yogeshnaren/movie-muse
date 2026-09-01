"""Unset Final Draft binary is unavailable, never pytest.skip."""

from __future__ import annotations

import os

import pytest

from movie_muse.fdx.api import (
    FINAL_DRAFT_BIN_ENV,
    FdxService,
    FinalDraftUnavailableError,
)
from movie_muse.testkit.api import FixtureCatalog


def test_final_draft_unavailable_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FINAL_DRAFT_BIN_ENV, raising=False)
    service = FdxService()
    assert service.final_draft_available() is False
    with pytest.raises(FinalDraftUnavailableError):
        service.require_final_draft()
    with pytest.raises(FinalDraftUnavailableError):
        service.final_draft_round_trip(FixtureCatalog().get("small_kitchen").document)


def test_final_draft_missing_path_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FINAL_DRAFT_BIN_ENV, "/nonexistent/FinalDraft")
    with pytest.raises(FinalDraftUnavailableError):
        FdxService().require_final_draft()


def test_ext_gate_env_name_is_stable() -> None:
    assert FINAL_DRAFT_BIN_ENV == "MOVIE_MUSE_FINAL_DRAFT_BIN"
    assert FINAL_DRAFT_BIN_ENV not in os.environ or not os.path.exists(os.environ[FINAL_DRAFT_BIN_ENV])
