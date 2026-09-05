"""Typed editor commands, modes, and projections. Not canonical state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class AuthorMode(str, Enum):
    """Distraction-safe authoring vs review chrome. Never forks project state."""

    AUTHOR = "author"
    REVIEW = "review"


class ContextualAction(str, Enum):
    PRESERVE = "preserve"
    EXPLORE = "explore"
    LOCK = "lock"
    INTENT = "intent"


class ElementKind(str, Enum):
    SCENE_HEADING = "scene_heading"
    ACTION = "action"
    CHARACTER = "character"
    PARENTHETICAL = "parenthetical"
    DIALOGUE = "dialogue"
    TRANSITION = "transition"
    SHOT = "shot"
    GENERAL = "general"
    LYRICS = "lyrics"
    PAGE_BREAK = "page_break"
    TITLE_PAGE_ELEMENT = "title_page_element"


# Enter/Tab transitions. Values are the next authored element kind.
ENTER_TRANSITIONS: dict[str, str] = {
    ElementKind.SCENE_HEADING.value: ElementKind.ACTION.value,
    ElementKind.ACTION.value: ElementKind.ACTION.value,
    ElementKind.CHARACTER.value: ElementKind.DIALOGUE.value,
    ElementKind.PARENTHETICAL.value: ElementKind.DIALOGUE.value,
    ElementKind.DIALOGUE.value: ElementKind.ACTION.value,
    ElementKind.TRANSITION.value: ElementKind.SCENE_HEADING.value,
    ElementKind.SHOT.value: ElementKind.ACTION.value,
    ElementKind.GENERAL.value: ElementKind.ACTION.value,
    ElementKind.LYRICS.value: ElementKind.ACTION.value,
}

TAB_TRANSITIONS: dict[str, str] = {
    ElementKind.ACTION.value: ElementKind.CHARACTER.value,
    ElementKind.CHARACTER.value: ElementKind.ACTION.value,
    ElementKind.DIALOGUE.value: ElementKind.PARENTHETICAL.value,
    ElementKind.PARENTHETICAL.value: ElementKind.DIALOGUE.value,
    ElementKind.SCENE_HEADING.value: ElementKind.ACTION.value,
    ElementKind.TRANSITION.value: ElementKind.ACTION.value,
}


@dataclass(frozen=True, slots=True)
class OutlineEntry:
    scene_id: str
    scene_number: str
    heading: str
    block_id: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "scene_number": self.scene_number,
            "heading": self.heading,
            "block_id": self.block_id,
            "summary": self.summary,
        }


@dataclass(frozen=True, slots=True)
class SceneCard:
    scene_id: str
    heading: str
    summary: str
    block_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "heading": self.heading,
            "summary": self.summary,
            "block_ids": list(self.block_ids),
        }


@dataclass(frozen=True, slots=True)
class SearchHit:
    block_id: str
    offset: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"block_id": self.block_id, "offset": self.offset, "text": self.text}


@dataclass(frozen=True, slots=True)
class AutocompleteSuggestion:
    kind: str
    text: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "text": self.text, "source": self.source}


@dataclass(frozen=True, slots=True)
class AccessibilityContract:
    role: str
    label: str
    reading_order: tuple[str, ...]
    live_region: str = "polite"

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "label": self.label,
            "reading_order": list(self.reading_order),
            "live_region": self.live_region,
        }
