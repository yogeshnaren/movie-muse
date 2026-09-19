"""Pure layout engine: document + profiles + locks + version → LayoutResult."""

from __future__ import annotations

from dataclasses import dataclass, replace

from movie_muse.document.api import normalize, semantic_validate
from movie_muse.layout.errors import LayoutEngineError, LockedPaginationError
from movie_muse.layout.hashing import hash_payload, input_hash
from movie_muse.layout.locks import (
    ab_overflow_number,
    assert_locks_honored,
    lock_state_from_document,
    next_page_number,
    parse_page_number,
)
from movie_muse.layout.metrics import CPI, FONT_METRICS_VERSION, LAYOUT_ENGINE_VERSION, cells_for
from movie_muse.layout.profiles import resolve_paper_profile, resolve_style_profile
from movie_muse.layout.types import (
    LayoutLine,
    LayoutObservation,
    LayoutPage,
    LayoutResult,
    LayoutTraceEvent,
    PaperProfile,
    ProductionLockState,
    StyleProfile,
)
from movie_muse.layout.wrap import wrap_text
from movie_muse.schemas.api import Block, BlockKind, ScreenplayDocument

# Professional screenplay insets in inches from the left edge of the paper.
_ELEMENT_BOX: dict[str, tuple[float, float]] = {
    BlockKind.SCENE_HEADING.value: (1.5, 6.0),
    BlockKind.ACTION.value: (1.5, 6.0),
    BlockKind.CHARACTER.value: (3.7, 2.0),
    BlockKind.PARENTHETICAL.value: (3.1, 2.0),
    BlockKind.DIALOGUE.value: (2.5, 3.5),
    BlockKind.TRANSITION.value: (6.0, 1.5),
    BlockKind.SHOT.value: (1.5, 6.0),
    BlockKind.GENERAL.value: (1.5, 6.0),
    BlockKind.LYRICS.value: (2.5, 3.5),
    BlockKind.TITLE_PAGE_ELEMENT.value: (1.5, 6.0),
    BlockKind.PAGE_BREAK.value: (1.5, 6.0),
}


@dataclass
class _RawLine:
    text: str
    x_chars: int
    width_chars: int
    line_kind: str
    block_id: str | None
    block_kind: str | None
    scene_id: str | None
    scene_number: str | None
    revision_color: str | None
    revision_mark: bool
    locked: bool
    synthetic: bool
    source_block_ids: tuple[str, ...]
    continuation: str | None = None
    assigned_page: str | None = None
    y_line: int = 0
    row: int | None = None


@dataclass
class _Group:
    kind: str
    lines: list[_RawLine]
    assigned_page: str | None = None
    character_text: str | None = None
    character_block_id: str | None = None
    character_x: int = 37
    character_width: int = 20
    scene_id: str | None = None
    scene_number: str | None = None
    leading_blank: bool = False
    source_block_id: str | None = None


def layout_document(
    document: ScreenplayDocument,
    style_profile: StyleProfile | str | None = None,
    paper_profile: PaperProfile | str | None = None,
    production_lock_state: ProductionLockState | None = None,
    engine_version: str = LAYOUT_ENGINE_VERSION,
) -> LayoutResult:
    """Deterministic layout. Identical inputs produce identical hashes/bytes."""

    if engine_version != LAYOUT_ENGINE_VERSION:
        raise LayoutEngineError(f"unsupported layout engine version: {engine_version!r}")
    canonical = normalize(document)
    semantic_validate(canonical)
    style = resolve_style_profile(style_profile or canonical.style)
    paper = resolve_paper_profile(paper_profile or canonical.paper_size)
    lock_state = production_lock_state or lock_state_from_document(canonical)
    digest = input_hash(canonical, style, paper, lock_state, engine_version=engine_version)
    pages, traces, block_pages = _paginate(canonical, style, paper, lock_state)
    assert_locks_honored(lock_state=lock_state, block_pages=block_pages)
    _assert_scene_numbers_locked(canonical, lock_state)
    lines = tuple(line for page in pages for line in page.lines)
    payload = {
        "engine_version": engine_version,
        "font_metrics_version": FONT_METRICS_VERSION,
        "style_profile_id": style.id,
        "paper_profile_id": paper.id,
        "pages": [page.to_dict() for page in pages],
        "traces": [event.to_dict() for event in traces],
    }
    layout_digest = hash_payload(payload)
    observation = LayoutObservation(
        input_hash=digest,
        layout_hash=layout_digest,
        page_count=len(pages),
        line_count=len(lines),
        engine_version=engine_version,
        font_metrics_version=FONT_METRICS_VERSION,
        lock_honored=True,
    )
    return LayoutResult(
        pages=tuple(pages),
        lines=lines,
        traces=tuple(traces),
        input_hash=digest,
        layout_hash=layout_digest,
        engine_version=engine_version,
        font_metrics_version=FONT_METRICS_VERSION,
        style_profile_id=style.id,
        paper_profile_id=paper.id,
        observation=observation,
    )


def _assert_scene_numbers_locked(document: ScreenplayDocument, lock_state: ProductionLockState) -> None:
    if not lock_state.scene_numbers_locked:
        return
    expected = {scene.scene_id: scene.scene_number for scene in lock_state.locked_scenes}
    if not expected:
        return
    for block in document.blocks:
        if block.kind is not BlockKind.SCENE_HEADING or block.scene_id not in expected:
            continue
        if (block.scene_number or "") != expected[block.scene_id]:
            raise LockedPaginationError(
                f"locked scene {block.scene_id} number changed to {block.scene_number!r}"
            )


def _box(kind: str, paper: PaperProfile) -> tuple[int, int]:
    left_in, width_in = _ELEMENT_BOX.get(kind, (paper.left_margin_in, paper.usable_width_in))
    return (int(round(left_in * CPI)), int(round(width_in * CPI)))


def _extras(block: Block) -> dict[str, object]:
    raw = block.unknown_extensions
    return dict(raw) if raw else {}


def _is_omitted(block: Block) -> bool:
    extras = _extras(block)
    return bool(extras.get("omitted_scene") or block.is_boneyard)


def _assigned_page(block: Block) -> str | None:
    extras = _extras(block)
    value = extras.get("page_lock") or extras.get("page_number")
    return str(value) if value else None


def _is_locked_page(block: Block) -> bool:
    return bool(_extras(block).get("locked_page"))


def _revision_for(block: Block, document: ScreenplayDocument) -> tuple[str | None, bool]:
    if not block.revision_mark_ids:
        return (None, False)
    marks = {mark.id: mark for mark in document.revision_marks}
    for mark_id in block.revision_mark_ids:
        mark = marks.get(mark_id)
        if mark is not None:
            return (mark.revision_color, True)
    return (None, True)


def _raw_from_block(
    block: Block,
    document: ScreenplayDocument,
    paper: PaperProfile,
    text: str,
    *,
    line_kind: str,
    synthetic: bool = False,
    continuation: str | None = None,
) -> _RawLine:
    x_chars, width_chars = _box(block.kind.value, paper)
    color, marked = _revision_for(block, document)
    return _RawLine(
        text=text,
        x_chars=x_chars,
        width_chars=width_chars,
        line_kind=line_kind,
        block_id=block.id,
        block_kind=block.kind.value,
        scene_id=block.scene_id,
        scene_number=block.scene_number,
        revision_color=color,
        revision_mark=marked,
        locked=_is_locked_page(block) or bool(_extras(block).get("locked_scene")),
        synthetic=synthetic,
        source_block_ids=(block.id,),
        continuation=continuation,
        assigned_page=_assigned_page(block) if _is_locked_page(block) else None,
    )


def _wrap_block(block: Block, document: ScreenplayDocument, paper: PaperProfile) -> list[_RawLine]:
    _x, width = _box(block.kind.value, paper)
    wrapped = wrap_text(block.text, width)
    return [_raw_from_block(block, document, paper, line, line_kind="content") for line in wrapped]


def _build_groups(
    document: ScreenplayDocument,
    style: StyleProfile,
    paper: PaperProfile,
) -> list[_Group]:
    groups: list[_Group] = []
    blocks = list(document.blocks)
    index = 0
    seen_omitted: set[str] = set()
    while index < len(blocks):
        block = blocks[index]
        if block.kind is BlockKind.PAGE_BREAK:
            groups.append(
                _Group(
                    kind="break",
                    lines=[],
                    assigned_page=_assigned_page(block),
                    source_block_id=block.id,
                )
            )
            index += 1
            continue
        if block.kind is BlockKind.TITLE_PAGE_ELEMENT:
            title_lines = _wrap_block(block, document, paper)
            for line in title_lines:
                line.line_kind = "title"
                usable = int(round(paper.usable_width_in * CPI))
                pad = max(0, (usable - cells_for(line.text)) // 2)
                line.x_chars = int(round(paper.left_margin_in * CPI)) + pad
            groups.append(
                _Group(kind="title", lines=title_lines, leading_blank=False, source_block_id=block.id)
            )
            index += 1
            continue
        if _is_omitted(block) and block.kind is BlockKind.SCENE_HEADING:
            scene_key = block.scene_id or block.id
            if scene_key not in seen_omitted:
                seen_omitted.add(scene_key)
                number = block.scene_number or ""
                text = f"{number}    {style.omitted_text}".strip()
                line = _raw_from_block(block, document, paper, text, line_kind="omitted")
                groups.append(
                    _Group(
                        kind="omitted",
                        lines=[line],
                        scene_id=block.scene_id,
                        scene_number=block.scene_number,
                        leading_blank=bool(groups),
                        source_block_id=block.id,
                    )
                )
            index += 1
            while (
                index < len(blocks)
                and _is_omitted(blocks[index])
                and blocks[index].kind is not BlockKind.SCENE_HEADING
            ):
                index += 1
            continue
        if _is_omitted(block):
            index += 1
            continue
        if block.is_dual_dialogue:
            dual_blocks, index = _collect_dual(blocks, index)
            groups.append(_dual_group(dual_blocks, document, paper, leading_blank=bool(groups)))
            continue
        if block.kind is BlockKind.CHARACTER:
            chain, index = _collect_dialogue_chain(blocks, index)
            groups.append(_dialogue_group(chain, document, paper, style, leading_blank=bool(groups)))
            continue
        lines = _wrap_block(block, document, paper)
        if block.kind is BlockKind.SCENE_HEADING and block.scene_number:
            left = _raw_from_block(block, document, paper, block.scene_number, line_kind="scene_number")
            left.x_chars = 9
            left.width_chars = 4
            heading = (
                lines[0]
                if lines
                else _raw_from_block(block, document, paper, block.text, line_kind="content")
            )
            group_lines = [left, heading, *lines[1:]]
        else:
            group_lines = lines
        groups.append(
            _Group(
                kind="block",
                lines=group_lines,
                assigned_page=_assigned_page(block) if _is_locked_page(block) else None,
                scene_id=block.scene_id,
                scene_number=block.scene_number,
                leading_blank=bool(groups),
                source_block_id=block.id,
            )
        )
        index += 1
    return groups


def _collect_dialogue_chain(blocks: list[Block], start: int) -> tuple[list[Block], int]:
    chain = [blocks[start]]
    index = start + 1
    follow = {
        BlockKind.PARENTHETICAL.value,
        BlockKind.DIALOGUE.value,
        BlockKind.LYRICS.value,
    }
    while index < len(blocks) and blocks[index].kind.value in follow:
        if blocks[index].is_dual_dialogue:
            break
        chain.append(blocks[index])
        index += 1
    return chain, index


def _collect_dual(blocks: list[Block], start: int) -> tuple[list[Block], int]:
    group_id = blocks[start].dual_dialogue_group_id
    collected = [blocks[start]]
    index = start + 1
    while (
        index < len(blocks)
        and blocks[index].is_dual_dialogue
        and blocks[index].dual_dialogue_group_id == group_id
    ):
        collected.append(blocks[index])
        index += 1
    return collected, index


def _dialogue_group(
    chain: list[Block],
    document: ScreenplayDocument,
    paper: PaperProfile,
    style: StyleProfile,
    *,
    leading_blank: bool,
) -> _Group:
    lines: list[_RawLine] = []
    character = chain[0]
    char_lines = _wrap_block(character, document, paper)
    if character.is_continued or _extras(character).get("contd"):
        char_lines[0].text = f"{char_lines[0].text} {style.contd_suffix}"
        char_lines[0].continuation = "contd"
    lines.extend(char_lines)
    for block in chain[1:]:
        lines.extend(_wrap_block(block, document, paper))
    x_chars, width_chars = _box(BlockKind.CHARACTER.value, paper)
    assigned = None
    for item in chain:
        if _is_locked_page(item):
            assigned = _assigned_page(item)
            break
    return _Group(
        kind="dialogue",
        lines=lines,
        assigned_page=assigned,
        character_text=character.text,
        character_block_id=character.id,
        character_x=x_chars,
        character_width=width_chars,
        scene_id=character.scene_id,
        leading_blank=leading_blank,
        source_block_id=character.id,
    )


def _dual_group(
    blocks: list[Block],
    document: ScreenplayDocument,
    paper: PaperProfile,
    *,
    leading_blank: bool,
) -> _Group:
    characters = [block for block in blocks if block.kind is BlockKind.CHARACTER]
    split_at = characters[1].id if len(characters) > 1 else None
    left: list[Block] = []
    right: list[Block] = []
    bucket = left
    for block in blocks:
        if split_at and block.id == split_at:
            bucket = right
        bucket.append(block)
    left_lines = [line for block in left for line in _wrap_block(block, document, paper)]
    right_lines = [line for block in right for line in _wrap_block(block, document, paper)]
    left_x = int(round(1.5 * CPI))
    right_x = int(round(4.5 * CPI))
    col_width = int(round(2.5 * CPI))
    for line in left_lines:
        line.x_chars = left_x
        line.width_chars = col_width
        line.line_kind = "dual"
    for line in right_lines:
        line.x_chars = right_x
        line.width_chars = col_width
        line.line_kind = "dual"
    height = max(len(left_lines), len(right_lines))
    merged: list[_RawLine] = []
    for row in range(height):
        if row < len(left_lines):
            left_lines[row].row = row
            merged.append(left_lines[row])
        if row < len(right_lines):
            right_lines[row].row = row
            merged.append(right_lines[row])
    return _Group(
        kind="dual",
        lines=merged,
        leading_blank=leading_blank,
        source_block_id=blocks[0].id if blocks else None,
    )


def _paginate(
    document: ScreenplayDocument,
    style: StyleProfile,
    paper: PaperProfile,
    lock_state: ProductionLockState,
) -> tuple[list[LayoutPage], list[LayoutTraceEvent], dict[str, str]]:
    capacity = paper.body_lines
    reserved = lock_state.reserved_page_numbers() if lock_state.pages_locked else frozenset()
    traces: list[LayoutTraceEvent] = []
    pages: list[LayoutPage] = []
    block_pages: dict[str, str] = {}
    current_lines: list[_RawLine] = []
    current_number = ""
    title_mode = True

    def used() -> int:
        if not current_lines:
            return 0
        return max(line.y_line for line in current_lines) + 1

    def remaining() -> int:
        return capacity - used()

    def emit_group(group: _Group) -> None:
        if group.leading_blank and current_lines:
            blank = _blank_line(current_lines[-1])
            blank.y_line = used()
            current_lines.append(blank)
        if group.kind == "dual":
            base = used()
            for line in group.lines:
                line.y_line = base + (line.row or 0)
                current_lines.append(line)
        else:
            for line in group.lines:
                line.y_line = used()
                current_lines.append(line)
        for line in group.lines:
            if line.line_kind in {"content", "dual", "omitted", "title"}:
                traces.append(
                    LayoutTraceEvent(
                        op="place_line",
                        page_number=current_number,
                        block_id=line.block_id,
                        detail=line.line_kind,
                    )
                )
        if group.kind == "omitted":
            traces.append(
                LayoutTraceEvent(
                    op="omitted",
                    page_number=current_number,
                    block_id=group.lines[0].block_id if group.lines else None,
                    detail=group.scene_number or "",
                )
            )

    def close_page(*, continued_scene: str | None = None) -> None:
        nonlocal current_lines, current_number, title_mode
        if not current_lines and not current_number:
            return
        is_title = title_mode and current_lines and all(line.line_kind == "title" for line in current_lines)
        number = "" if is_title else (current_number or next_page_number("", reserved))
        page = _materialize_page(
            number,
            current_lines,
            style,
            paper,
            is_title=bool(is_title),
            continued_scene=continued_scene,
            reserved=reserved,
        )
        pages.append(page)
        for line in page.lines:
            if line.block_id:
                block_pages.setdefault(line.block_id, page.page_number)
        traces.append(LayoutTraceEvent(op="break_page", page_number=page.page_number, detail=page.header))
        current_lines = []
        current_number = ""
        if is_title:
            title_mode = False

    queue = list(_group_list(document, style, paper))
    while queue:
        group = queue.pop(0)
        if group.kind == "break":
            assigned = group.assigned_page if lock_state.pages_locked else None
            if assigned:
                if current_number and current_number != assigned and current_lines:
                    close_page()
                if not current_number:
                    current_number = assigned
            closed_as = current_number or assigned or ""
            close_page()
            if group.source_block_id and closed_as:
                block_pages.setdefault(group.source_block_id, closed_as)
            traces.append(
                LayoutTraceEvent(op="forced_break", page_number=closed_as, detail="page_break")
            )
            continue
        if group.kind == "title":
            if not title_mode and current_lines:
                close_page()
            needed = len(group.lines) + (1 if group.leading_blank and current_lines else 0)
            if needed > remaining() and current_lines:
                close_page()
            emit_group(group)
            continue
        if title_mode and current_lines:
            close_page()
        assigned = group.assigned_page if lock_state.pages_locked else None
        if assigned:
            if current_number and current_number != assigned and current_lines:
                close_page()
            if current_number and current_number != assigned:
                close_page()
            current_number = assigned
        needed = _group_height(group)
        if needed > remaining() and current_lines:
            if group.kind == "dialogue":
                placed = _split_dialogue(group, style, remaining(), traces, current_number)
                if placed is not None:
                    first, rest = placed
                    emit_group(first)
                    closed = current_number
                    close_page(continued_scene=group.scene_id)
                    current_number = _next_after_overflow(pages, reserved, lock_state, closed)
                    queue.insert(0, rest)
                    continue
            closed = current_number
            close_page(continued_scene=group.scene_id)
            current_number = _next_after_overflow(pages, reserved, lock_state, closed)
            queue.insert(0, group)
            continue
        if needed > remaining() and not current_lines:
            if group.kind == "dialogue":
                placed = _split_dialogue(group, style, remaining(), traces, current_number)
                if placed is not None:
                    current_number = current_number or assigned or _advance_number(pages, reserved, lock_state)
                    first, rest = placed
                    emit_group(first)
                    closed = current_number
                    close_page(continued_scene=group.scene_id)
                    current_number = _next_after_overflow(pages, reserved, lock_state, closed)
                    queue.insert(0, rest)
                    continue
            raise LayoutEngineError("group exceeds a full page and cannot be split")
        if not current_number:
            current_number = assigned or _advance_number(pages, reserved, lock_state)
        emit_group(group)
    close_page()
    titles = [page for page in pages if page.is_title_page]
    scripts = sorted(
        [page for page in pages if not page.is_title_page],
        key=lambda page: parse_page_number(page.page_number),
    )
    return [*titles, *scripts], traces, block_pages


def _group_list(
    document: ScreenplayDocument, style: StyleProfile, paper: PaperProfile
) -> list[_Group]:
    return _build_groups(document, style, paper)


def _group_height(group: _Group) -> int:
    extra = 1 if group.leading_blank else 0
    if group.kind == "dual":
        if not group.lines:
            return extra
        return extra + max((line.row or 0) for line in group.lines) + 1
    return extra + len(group.lines)


def _blank_line(previous: _RawLine | None) -> _RawLine:
    return _RawLine(
        text="",
        x_chars=previous.x_chars if previous else 15,
        width_chars=previous.width_chars if previous else 60,
        line_kind="blank",
        block_id=None,
        block_kind=None,
        scene_id=previous.scene_id if previous else None,
        scene_number=None,
        revision_color=None,
        revision_mark=False,
        locked=False,
        synthetic=True,
        source_block_ids=(),
    )


def _advance_number(
    pages: list[LayoutPage],
    reserved: frozenset[str],
    lock_state: ProductionLockState,
) -> str:
    previous = ""
    for page in reversed(pages):
        if not page.is_title_page:
            previous = page.page_number
            break
    nxt = next_page_number(previous, reserved)
    if nxt in reserved and lock_state.pages_locked:
        nxt = next_page_number(nxt, reserved)
    return nxt


def _next_after_overflow(
    pages: list[LayoutPage],
    reserved: frozenset[str],
    lock_state: ProductionLockState,
    closed_number: str,
) -> str:
    if lock_state.pages_locked and closed_number and closed_number in reserved:
        return ab_overflow_number(closed_number, reserved)
    return _advance_number(pages, reserved, lock_state)


def _split_dialogue(
    group: _Group,
    style: StyleProfile,
    remaining_lines: int,
    traces: list[LayoutTraceEvent],
    page_number: str,
) -> tuple[_Group, _Group] | None:
    if group.kind != "dialogue" or not group.character_text:
        return None
    head: list[_RawLine] = []
    dialogue_index = 0
    for index, line in enumerate(group.lines):
        head.append(line)
        if line.block_kind == BlockKind.DIALOGUE.value:
            dialogue_index = index
            break
    if not any(line.block_kind == BlockKind.DIALOGUE.value for line in group.lines):
        return None
    more_line = _RawLine(
        text=style.more_text,
        x_chars=int(round(2.5 * CPI)),
        width_chars=35,
        line_kind="more",
        block_id=group.lines[dialogue_index].block_id if dialogue_index < len(group.lines) else None,
        block_kind=BlockKind.DIALOGUE.value,
        scene_id=group.scene_id,
        scene_number=group.scene_number,
        revision_color=None,
        revision_mark=False,
        locked=False,
        synthetic=True,
        source_block_ids=tuple(line.block_id for line in group.lines if line.block_id),
        continuation="more",
    )
    min_needed = len(head) + 1 + (1 if group.leading_blank else 0)
    if remaining_lines < min_needed:
        return None
    budget = remaining_lines - (1 if group.leading_blank else 0) - 1
    take = max(len(head), min(budget, len(group.lines)))
    if take >= len(group.lines):
        return None
    first_lines = list(group.lines[:take])
    rest_source = group.lines[take:]
    if not any(line.block_kind == BlockKind.DIALOGUE.value for line in first_lines):
        return None
    first_lines.append(more_line)
    contd = _RawLine(
        text=f"{group.character_text} {style.contd_suffix}",
        x_chars=group.character_x,
        width_chars=group.character_width,
        line_kind="contd",
        block_id=group.character_block_id,
        block_kind=BlockKind.CHARACTER.value,
        scene_id=group.scene_id,
        scene_number=group.scene_number,
        revision_color=None,
        revision_mark=False,
        locked=False,
        synthetic=True,
        source_block_ids=(group.character_block_id,) if group.character_block_id else (),
        continuation="contd",
    )
    traces.append(LayoutTraceEvent(op="more", page_number=page_number, block_id=group.character_block_id))
    traces.append(LayoutTraceEvent(op="contd", page_number=page_number, block_id=group.character_block_id))
    first = replace(group, lines=first_lines)
    rest = replace(group, lines=[contd, *rest_source], leading_blank=False)
    return first, rest


def _materialize_page(
    number: str,
    raw_lines: list[_RawLine],
    style: StyleProfile,
    paper: PaperProfile,
    *,
    is_title: bool,
    continued_scene: str | None,
    reserved: frozenset[str],
) -> LayoutPage:
    _n, suffix = parse_page_number(number)
    header = "" if is_title else number
    footer = style.continued_text if continued_scene and not is_title else ""
    lines: list[LayoutLine] = []
    scene_ids: list[str] = []
    block_ids: list[str] = []
    colors: list[str] = []
    locked = number in reserved and not is_title
    for raw in raw_lines:
        line = LayoutLine(
            text=raw.text,
            page_number=number,
            y_line=raw.y_line,
            x_chars=raw.x_chars,
            width_chars=raw.width_chars,
            line_kind=raw.line_kind,
            block_id=raw.block_id,
            block_kind=raw.block_kind,
            scene_id=raw.scene_id,
            scene_number=raw.scene_number,
            continuation=raw.continuation,
            revision_color=raw.revision_color,
            revision_mark=raw.revision_mark,
            locked=raw.locked or locked,
            synthetic=raw.synthetic,
            source_block_ids=raw.source_block_ids,
        )
        lines.append(line)
        if raw.scene_id and raw.scene_id not in scene_ids:
            scene_ids.append(raw.scene_id)
        if raw.block_id and raw.block_id not in block_ids:
            block_ids.append(raw.block_id)
        if raw.revision_color and raw.revision_color not in colors:
            colors.append(raw.revision_color)
    if not is_title:
        header_line = LayoutLine(
            text=header,
            page_number=number,
            y_line=-1,
            x_chars=int(round((paper.width_in - paper.right_margin_in) * CPI)) - max(cells_for(header), 1),
            width_chars=max(cells_for(header), 1),
            line_kind="header",
            synthetic=True,
        )
        lines = [header_line, *lines]
        if footer:
            footer_y = max((raw.y_line for raw in raw_lines), default=-1) + 1
            footer_line = LayoutLine(
                text=footer,
                page_number=number,
                y_line=footer_y,
                x_chars=int(round(paper.left_margin_in * CPI)),
                width_chars=cells_for(footer),
                line_kind="footer",
                scene_id=continued_scene,
                continuation="continued",
                synthetic=True,
            )
            lines.append(footer_line)
    return LayoutPage(
        page_number=number,
        lines=tuple(lines),
        header=header,
        footer=footer,
        is_title_page=is_title,
        is_ab_page=bool(suffix),
        ab_suffix=suffix or None,
        locked=locked,
        scene_ids=tuple(scene_ids),
        block_ids=tuple(block_ids),
        revision_colors=tuple(colors),
    )
