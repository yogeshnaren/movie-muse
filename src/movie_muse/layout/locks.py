"""Extract and honor production lock state. Layout never silently unlocks."""

from __future__ import annotations

from movie_muse.layout.errors import LockedPaginationError
from movie_muse.layout.types import LockedPage, LockedScene, ProductionLockState
from movie_muse.schemas.api import Block, ScreenplayDocument


def _extras(block: Block) -> dict[str, object]:
    raw = block.unknown_extensions
    return dict(raw) if raw else {}


def lock_state_from_document(document: ScreenplayDocument) -> ProductionLockState:
    page_blocks: dict[str, list[str]] = {}
    scenes: list[LockedScene] = []
    seen_scenes: set[str] = set()
    for block in document.blocks:
        extras = _extras(block)
        page_number = extras.get("page_lock") or extras.get("page_number")
        if extras.get("locked_page") and page_number:
            page_blocks.setdefault(str(page_number), []).append(block.id)
        scene_id = block.scene_id
        if extras.get("locked_scene") and scene_id and scene_id not in seen_scenes:
            seen_scenes.add(scene_id)
            scenes.append(LockedScene(scene_id=scene_id, scene_number=block.scene_number or ""))
    pages = tuple(
        LockedPage(page_number=number, block_ids=tuple(block_ids))
        for number, block_ids in page_blocks.items()
    )
    return ProductionLockState(
        locked_pages=pages,
        locked_scenes=tuple(scenes),
        pages_locked=bool(pages),
        scene_numbers_locked=bool(scenes),
    )


def assert_locks_honored(
    *,
    lock_state: ProductionLockState,
    block_pages: dict[str, str],
) -> None:
    """Fail closed if a locked block landed on a different page number."""

    expected: dict[str, str] = {}
    for page in lock_state.locked_pages:
        for block_id in page.block_ids:
            expected[block_id] = page.page_number
    for block_id, page_number in expected.items():
        actual = block_pages.get(block_id)
        if actual is None:
            raise LockedPaginationError(
                f"locked block {block_id} is missing from layout; unlock is required to drop it"
            )
        if actual != page_number:
            raise LockedPaginationError(
                f"locked block {block_id} moved from page {page_number} to {actual}; "
                "unlocking or repagination requires explicit permission"
            )


def parse_page_number(value: str) -> tuple[int, str]:
    if not value:
        return (0, "")
    index = 0
    while index < len(value) and value[index].isdigit():
        index += 1
    if index == 0:
        return (0, value)
    return (int(value[:index]), value[index:])


def increment_suffix(suffix: str) -> str:
    if not suffix:
        return "A"
    letters = list(suffix)
    position = len(letters) - 1
    while position >= 0:
        if letters[position] != "Z":
            letters[position] = chr(ord(letters[position]) + 1)
            return "".join(letters)
        letters[position] = "A"
        position -= 1
    return "A" + "".join(letters)


def next_page_number(current: str, reserved: frozenset[str]) -> str:
    """Return the next production page number without colliding with locks."""

    if not current:
        candidate = "1"
        if candidate not in reserved:
            return candidate
        return next_page_number(candidate, reserved)
    number, suffix = parse_page_number(current)
    if suffix:
        candidate = f"{number}{increment_suffix(suffix)}"
        if candidate not in reserved:
            return candidate
        return next_page_number(candidate, reserved)
    integer = str(number + 1)
    if integer not in reserved:
        return integer
    ab = f"{number}A"
    while ab in reserved:
        _n, ab_suffix = parse_page_number(ab)
        ab = f"{number}{increment_suffix(ab_suffix)}"
    return ab


def ab_overflow_number(current: str, reserved: frozenset[str]) -> str:
    """Insert an A/B page after ``current`` without stealing a reserved integer."""

    number, suffix = parse_page_number(current)
    candidate = f"{number}{increment_suffix(suffix)}"
    while candidate in reserved:
        number, suffix = parse_page_number(candidate)
        candidate = f"{number}{increment_suffix(suffix)}"
    return candidate
