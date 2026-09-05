"""Pagination, locks, and sides workflows represented by Final Draft and Scriptation."""

from __future__ import annotations

from movie_muse.fdx.api import FdxService
from movie_muse.layout.api import LayoutService
from movie_muse.production_revisions.api import ProductionRevisionService
from movie_muse.schemas.api import BlockKind
from movie_muse.testkit.api import FixtureCatalog


def test_fd_pagination() -> None:
    document = FixtureCatalog().get("small_kitchen").document
    service = LayoutService()
    first = service.layout(document)
    second = service.layout(document)
    assert first.layout_hash == second.layout_hash
    assert first.input_hash == second.input_hash
    assert document.blocks[0].text == FixtureCatalog().get("small_kitchen").document.blocks[0].text


def test_fd_locks_revisions() -> None:
    production = FixtureCatalog().get("production_locked_sides").document
    imported, report = FdxService().import_bytes(FdxService().export_document(production))
    assert report.lossless
    assert {mark.revision_label for mark in imported.revision_marks} == {
        mark.revision_label for mark in production.revision_marks
    }
    overlays = ProductionRevisionService()
    labels = overlays.ab_scene_labels(production)
    omitted = overlays.omitted_scene_ids(production)
    assert isinstance(labels, tuple)
    assert isinstance(omitted, tuple)
    layout = LayoutService().layout(production)
    assert layout.layout_hash
    assert production.title == FixtureCatalog().get("production_locked_sides").document.title


def test_sc_sides() -> None:
    document = FixtureCatalog().get("production_locked_sides").document
    scene_ids = tuple(
        block.scene_id
        for block in document.blocks
        if block.kind is BlockKind.SCENE_HEADING and block.scene_id
    )[:1]
    packet = ProductionRevisionService().sides(document, scene_ids)
    assert packet.id.startswith("art_")
    assert packet.scene_ids == scene_ids
    assert packet.layout.script_pages()
    assert packet.layout.layout_hash
