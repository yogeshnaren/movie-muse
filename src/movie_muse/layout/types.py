"""Typed layout inputs and results. Layout is a pure function of these values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from movie_muse.schemas.api import dataclass_to_dict


@dataclass(frozen=True, slots=True)
class PaperProfile:
    id: str
    width_in: float
    height_in: float
    top_margin_in: float
    bottom_margin_in: float
    left_margin_in: float
    right_margin_in: float
    version: str = "1.0.0"

    @property
    def body_lines(self) -> int:
        usable = self.height_in - self.top_margin_in - self.bottom_margin_in
        return int(round(usable * 6.0))

    @property
    def usable_width_in(self) -> float:
        return self.width_in - self.left_margin_in - self.right_margin_in

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class StyleProfile:
    id: str
    font_family: str
    font_metrics_version: str
    point_size: int
    more_text: str = "(MORE)"
    contd_suffix: str = "(CONT'D)"
    continued_text: str = "(CONTINUED)"
    continued_header: str = "CONTINUED:"
    omitted_text: str = "OMITTED"
    version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class LockedPage:
    page_number: str
    block_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class LockedScene:
    scene_id: str
    scene_number: str

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class ProductionLockState:
    """Lock state is an input to layout, never silently rewritten by it."""

    locked_pages: tuple[LockedPage, ...] = ()
    locked_scenes: tuple[LockedScene, ...] = ()
    pages_locked: bool = False
    scene_numbers_locked: bool = False

    def reserved_page_numbers(self) -> frozenset[str]:
        return frozenset(page.page_number for page in self.locked_pages if page.page_number)

    def locked_block_ids(self) -> frozenset[str]:
        ids: set[str] = set()
        for page in self.locked_pages:
            ids.update(page.block_ids)
        return frozenset(ids)

    def locked_scene_ids(self) -> frozenset[str]:
        return frozenset(scene.scene_id for scene in self.locked_scenes)

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @classmethod
    def unlocked(cls) -> ProductionLockState:
        return cls()


@dataclass(frozen=True, slots=True)
class LayoutLine:
    text: str
    page_number: str
    y_line: int
    x_chars: int
    width_chars: int
    line_kind: str
    block_id: str | None = None
    block_kind: str | None = None
    scene_id: str | None = None
    scene_number: str | None = None
    continuation: str | None = None
    revision_color: str | None = None
    revision_mark: bool = False
    locked: bool = False
    synthetic: bool = False
    source_block_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class LayoutPage:
    page_number: str
    lines: tuple[LayoutLine, ...]
    header: str
    footer: str
    is_title_page: bool = False
    is_ab_page: bool = False
    ab_suffix: str | None = None
    locked: bool = False
    scene_ids: tuple[str, ...] = ()
    block_ids: tuple[str, ...] = ()
    revision_colors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    @property
    def label(self) -> str:
        return self.page_number or "title"


@dataclass(frozen=True, slots=True)
class LayoutTraceEvent:
    op: str
    page_number: str
    block_id: str | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class LayoutObservation:
    """Operational metrics. Never includes screenplay text."""

    input_hash: str
    layout_hash: str
    page_count: int
    line_count: int
    engine_version: str
    font_metrics_version: str
    lock_honored: bool

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)


@dataclass(frozen=True, slots=True)
class LayoutResult:
    pages: tuple[LayoutPage, ...]
    lines: tuple[LayoutLine, ...]
    traces: tuple[LayoutTraceEvent, ...]
    input_hash: str
    layout_hash: str
    engine_version: str
    font_metrics_version: str
    style_profile_id: str
    paper_profile_id: str
    observation: LayoutObservation

    def to_dict(self) -> dict[str, Any]:
        return dataclass_to_dict(self)

    def script_pages(self) -> tuple[LayoutPage, ...]:
        return tuple(page for page in self.pages if not page.is_title_page)
