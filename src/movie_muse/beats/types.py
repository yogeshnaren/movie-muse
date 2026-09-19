"""Frameworks, story-function slots, mappings, and accessible themes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FrameworkKind(str, Enum):
    THREE_ACT = "three_act"
    SAVE_THE_CAT = "save_the_cat"
    HEROS_JOURNEY = "heros_journey"
    CUSTOM = "custom"


class MappingStatus(str, Enum):
    SUGGESTED = "suggested"
    MAPPED = "mapped"
    OVERRIDDEN = "overridden"
    NOT_APPLICABLE = "not_applicable"


class SlotFill(str, Enum):
    EMPTY = "empty"
    SUGGESTED = "suggested"
    MAPPED = "mapped"
    OVERRIDDEN = "overridden"
    NOT_APPLICABLE = "not_applicable"


LICENSED_KINDS = frozenset({FrameworkKind.SAVE_THE_CAT, FrameworkKind.HEROS_JOURNEY})
ADVISORY_DISCLAIMER = "Beat frameworks are guidance, not prescriptive truth."
MIN_CONTRAST_RATIO = 4.5


def _srgb_channel(value: int) -> float:
    channel = value / 255.0
    if channel <= 0.03928:
        return channel / 12.92
    return float(((channel + 0.055) / 1.055) ** 2.4)


def relative_luminance(hex_color: str) -> float:
    raw = hex_color.strip().lstrip("#")
    if len(raw) != 6:
        raise ValueError(f"expected #RRGGBB color, got {hex_color!r}")
    red = int(raw[0:2], 16)
    green = int(raw[2:4], 16)
    blue = int(raw[4:6], 16)
    return float(
        0.2126 * _srgb_channel(red)
        + 0.7152 * _srgb_channel(green)
        + 0.0722 * _srgb_channel(blue)
    )


def contrast_ratio(foreground: str, background: str) -> float:
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    lighter = max(first, second)
    darker = min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


@dataclass(frozen=True, slots=True)
class ColorToken:
    key: str
    background: str
    foreground: str
    pattern: str
    label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "background": self.background,
            "foreground": self.foreground,
            "pattern": self.pattern,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ColorToken:
        return cls(
            key=str(data["key"]),
            background=str(data["background"]),
            foreground=str(data["foreground"]),
            pattern=str(data["pattern"]),
            label=str(data["label"]),
        )


@dataclass(frozen=True, slots=True)
class ColorTheme:
    id: str
    name: str
    tokens: tuple[ColorToken, ...]
    accessible: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "tokens": [item.to_dict() for item in self.tokens],
            "accessible": self.accessible,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ColorTheme:
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            tokens=tuple(ColorToken.from_dict(item) for item in data.get("tokens", ())),
            accessible=bool(data.get("accessible", True)),
        )


@dataclass(frozen=True, slots=True)
class BeatSlot:
    id: str
    key: str
    label: str
    order: int
    guidance: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "key": self.key,
            "label": self.label,
            "order": self.order,
            "guidance": self.guidance,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeatSlot:
        return cls(
            id=str(data["id"]),
            key=str(data["key"]),
            label=str(data["label"]),
            order=int(data["order"]),
            guidance=str(data["guidance"]),
        )


@dataclass(frozen=True, slots=True)
class SlotMapping:
    id: str
    framework_id: str
    slot_key: str
    status: MappingStatus
    confidence: float
    scene_id: str | None = None
    story_function: str = ""
    suggested_scene_id: str | None = None
    override_reason: str = ""
    actor_id: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "framework_id": self.framework_id,
            "slot_key": self.slot_key,
            "status": self.status.value,
            "confidence": self.confidence,
            "scene_id": self.scene_id,
            "story_function": self.story_function,
            "suggested_scene_id": self.suggested_scene_id,
            "override_reason": self.override_reason,
            "actor_id": self.actor_id,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SlotMapping:
        return cls(
            id=str(data["id"]),
            framework_id=str(data["framework_id"]),
            slot_key=str(data["slot_key"]),
            status=MappingStatus(str(data["status"])),
            confidence=float(data["confidence"]),
            scene_id=str(data["scene_id"]) if data.get("scene_id") else None,
            story_function=str(data.get("story_function", "")),
            suggested_scene_id=(
                str(data["suggested_scene_id"]) if data.get("suggested_scene_id") else None
            ),
            override_reason=str(data.get("override_reason", "")),
            actor_id=str(data.get("actor_id", "")),
            updated_at=str(data.get("updated_at", "")),
        )


@dataclass(frozen=True, slots=True)
class SlotCompletion:
    slot_key: str
    label: str
    fill: SlotFill
    confidence: float
    scene_id: str | None
    color_token_key: str
    text_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_key": self.slot_key,
            "label": self.label,
            "fill": self.fill.value,
            "confidence": self.confidence,
            "scene_id": self.scene_id,
            "color_token_key": self.color_token_key,
            "text_status": self.text_status,
        }


@dataclass(frozen=True, slots=True)
class CompletionView:
    framework_id: str
    slots: tuple[SlotCompletion, ...]
    mapped_ratio: float
    mean_confidence: float
    guidance_not_truth: bool
    disclaimer: str
    theme_id: str
    formula_score: None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "framework_id": self.framework_id,
            "slots": [item.to_dict() for item in self.slots],
            "mapped_ratio": self.mapped_ratio,
            "mean_confidence": self.mean_confidence,
            "guidance_not_truth": self.guidance_not_truth,
            "disclaimer": self.disclaimer,
            "theme_id": self.theme_id,
            "formula_score": self.formula_score,
        }


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    kind: FrameworkKind
    title: str
    rights_required: bool
    slot_count: int
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "title": self.title,
            "rights_required": self.rights_required,
            "slot_count": self.slot_count,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class BeatFramework:
    id: str
    project_id: str
    kind: FrameworkKind
    title: str
    created_at: str
    created_by_actor_id: str
    slots: tuple[BeatSlot, ...]
    mappings: tuple[SlotMapping, ...] = ()
    theme_id: str = "thm_high_contrast_dark"
    source_id: str | None = None
    config_node_id: str | None = None
    analysis_node_id: str | None = None
    guidance_not_truth: bool = True
    disclaimer: str = ADVISORY_DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "kind": self.kind.value,
            "title": self.title,
            "created_at": self.created_at,
            "created_by_actor_id": self.created_by_actor_id,
            "slots": [item.to_dict() for item in self.slots],
            "mappings": [item.to_dict() for item in self.mappings],
            "theme_id": self.theme_id,
            "source_id": self.source_id,
            "config_node_id": self.config_node_id,
            "analysis_node_id": self.analysis_node_id,
            "guidance_not_truth": self.guidance_not_truth,
            "disclaimer": self.disclaimer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BeatFramework:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            kind=FrameworkKind(str(data["kind"])),
            title=str(data["title"]),
            created_at=str(data["created_at"]),
            created_by_actor_id=str(data["created_by_actor_id"]),
            slots=tuple(BeatSlot.from_dict(item) for item in data.get("slots", ())),
            mappings=tuple(SlotMapping.from_dict(item) for item in data.get("mappings", ())),
            theme_id=str(data.get("theme_id", "thm_high_contrast_dark")),
            source_id=str(data["source_id"]) if data.get("source_id") else None,
            config_node_id=(
                str(data["config_node_id"]) if data.get("config_node_id") else None
            ),
            analysis_node_id=(
                str(data["analysis_node_id"]) if data.get("analysis_node_id") else None
            ),
            guidance_not_truth=bool(data.get("guidance_not_truth", True)),
            disclaimer=str(data.get("disclaimer", ADVISORY_DISCLAIMER)),
        )
