"""FDX → Movie Muse → FDX semantic round trip over MM-012 screenplay fixtures."""

from __future__ import annotations

from movie_muse.document.api import normalize
from movie_muse.fdx.api import FdxService
from movie_muse.testkit.api import FixtureCatalog


def test_corpus_round_trip_is_lossless() -> None:
    service = FdxService()
    for fixture in FixtureCatalog().fixtures():
        exported = service.export_document(fixture.document)
        imported, report = service.import_bytes(exported)
        assert report.lossless, (fixture.manifest.id, report.to_dict())
        service.assert_lossless(fixture.document, imported)
        again = service.export_document(imported)
        assert again == exported


def test_notes_dual_dialogue_tags_revisions_locks_preserved() -> None:
    service = FdxService()
    catalog = FixtureCatalog()
    production = catalog.get("production_locked_sides").document
    harbor = catalog.get("feature_complete_harbor").document
    imported, report = service.import_bytes(service.export_document(production))
    assert report.lossless
    source = normalize(production)
    dual_imported, dual_report = service.import_bytes(service.export_document(harbor))
    assert dual_report.lossless
    assert any(block.is_dual_dialogue for block in dual_imported.blocks)
    assert {note.text for note in imported.notes} == {note.text for note in source.notes}
    assert {tag.value for tag in imported.production_tags} == {tag.value for tag in source.production_tags}
    assert {mark.revision_label for mark in imported.revision_marks} == {
        mark.revision_label for mark in source.revision_marks
    }
    locked = [
        block
        for block in imported.blocks
        if block.unknown_extensions.get("locked_scene") or block.unknown_extensions.get("locked_page")
    ]
    assert locked
    omitted = [block for block in imported.blocks if block.unknown_extensions.get("omitted_scene")]
    assert omitted
    ab = {block.unknown_extensions.get("ab_scene") for block in imported.blocks}
    assert "A" in ab and "B" in ab
    assert dual_imported.attachments
    assert {att.id for att in dual_imported.attachments} == {att.id for att in harbor.attachments}


def test_unicode_rtl_survives_round_trip() -> None:
    service = FdxService()
    document = FixtureCatalog().get("adversarial_unicode_rtl").document
    imported, report = service.import_bytes(service.export_document(document))
    assert report.lossless
    assert [block.text for block in imported.blocks] == [block.text for block in document.blocks]
