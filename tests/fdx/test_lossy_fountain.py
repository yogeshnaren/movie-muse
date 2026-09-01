"""Fountain/plain-text imports are lossy and must disclose before save/export."""

from __future__ import annotations

import pytest

from movie_muse.fdx.api import FdxService, PdfImportUnavailableError

FOUNTAIN = """Title: THE LOCK
Author: Jordan Hale

INT. KITCHEN - DAY

Ada tests the latch.

ADA
(quietly)
It holds.

CUT TO:

EXT. ALLEY - NIGHT

Rain.
"""


def test_fountain_import_returns_visible_loss_report() -> None:
    service = FdxService()
    document, report = service.import_fountain(FOUNTAIN)
    assert not report.lossless
    assert report.pathway == "fountain"
    codes = {item.code for item in report.items}
    assert "production_metadata_dropped" in codes
    kinds = [block.kind.value for block in document.blocks]
    assert "scene_heading" in kinds
    assert "character" in kinds
    assert "dialogue" in kinds
    assert "transition" in kinds
    assert document.title == "THE LOCK"


def test_plain_text_import_is_lossy() -> None:
    service = FdxService()
    document, report = service.import_plain_text("INT. OFFICE - DAY\n\nSomeone types.")
    assert not report.lossless
    assert report.pathway == "plain_text"
    assert document.blocks


def test_pdf_import_fails_closed() -> None:
    with pytest.raises(PdfImportUnavailableError):
        FdxService().import_pdf(b"%PDF-1.4")


def test_fountain_import_then_fdx_round_trip() -> None:
    service = FdxService()
    document, report = service.import_fountain(FOUNTAIN)
    assert not report.lossless
    exported = service.export_document(document)
    imported, fdx_report = service.import_bytes(exported)
    service.assert_lossless(document, imported)
    assert fdx_report.lossless
