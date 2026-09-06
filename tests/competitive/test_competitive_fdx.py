"""FDX handoff represented by Final Draft. Licensed binary stays external."""

from __future__ import annotations

import os

import pytest

from movie_muse.fdx.api import (
    FINAL_DRAFT_BIN_ENV,
    FdxService,
    FinalDraftUnavailableError,
    require_final_draft,
)
from movie_muse.testkit.api import FixtureCatalog


def test_fd_fdx_profile() -> None:
    service = FdxService()
    document = FixtureCatalog().get("feature_complete_harbor").document
    exported = service.export_document(document)
    imported, report = service.import_bytes(exported)
    assert report.lossless
    service.assert_lossless(document, imported)
    assert service.export_document(imported) == exported


def test_licensed_final_draft_gate_is_unset() -> None:
    """EXT-FDX-FINAL-DRAFT remains NOT_RUN. Unset binary must fail closed."""

    os.environ.pop(FINAL_DRAFT_BIN_ENV, None)
    with pytest.raises(FinalDraftUnavailableError):
        require_final_draft()
