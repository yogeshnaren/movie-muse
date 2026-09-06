"""Locked pages/scenes fail closed without authorized repagination."""

from __future__ import annotations

import pytest

from movie_muse.layout.api import (
    LayoutService,
    LockedPage,
    LockedPaginationError,
    ProductionLockState,
    lock_state_from_document,
)
from movie_muse.testkit.api import FixtureCatalog


def test_locked_page_content_lands_on_requested_page() -> None:
    document = FixtureCatalog().get("production_locked_sides").document
    result = LayoutService().layout(document)
    locked_lines = [
        line
        for line in result.lines
        if line.block_id
        and any(
            block.id == line.block_id and block.unknown_extensions.get("locked_page")
            for block in document.blocks
        )
    ]
    assert locked_lines
    assert all(line.page_number.startswith("10") for line in locked_lines)
    assert any(page.page_number == "10" and page.locked for page in result.script_pages())


def test_unlocked_state_allows_repagination() -> None:
    document = FixtureCatalog().get("production_locked_sides").document
    locked = LayoutService().layout(document)
    unlocked = LayoutService().layout(document, production_lock_state=ProductionLockState.unlocked())
    locked_block = next(
        block.id for block in document.blocks if block.unknown_extensions.get("locked_page")
    )
    locked_page = next(line.page_number for line in locked.lines if line.block_id == locked_block)
    unlocked_page = next(line.page_number for line in unlocked.lines if line.block_id == locked_block)
    assert locked_page.startswith("10")
    assert not unlocked_page.startswith("10")
    assert unlocked.layout_hash != locked.layout_hash


def test_lock_mismatch_fails_closed() -> None:
    document = FixtureCatalog().get("production_locked_sides").document
    derived = lock_state_from_document(document)
    wrong = ProductionLockState(
        locked_pages=(LockedPage(page_number="5", block_ids=derived.locked_pages[0].block_ids),),
        locked_scenes=derived.locked_scenes,
        pages_locked=True,
        scene_numbers_locked=True,
    )
    with pytest.raises(LockedPaginationError):
        LayoutService().layout(document, production_lock_state=wrong)


def test_locked_scene_numbers_are_honored() -> None:
    document = FixtureCatalog().get("production_locked_sides").document
    result = LayoutService().layout(document)
    derived = lock_state_from_document(document)
    assert derived.scene_numbers_locked
    for scene in derived.locked_scenes:
        assert any(line.scene_id == scene.scene_id and line.scene_number == scene.scene_number for line in result.lines)
