"""Palettes, rules, safety reviews, and ShotIR color proposals."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

DISCLAIMER = (
    "Observed palette correlations are not claimed as causation. "
    "This language is advisory visual guidance, not a proven audience effect."
)
FORBIDDEN_CAUSATION_PHRASES = (
    "causes the audience",
    "this palette makes them feel",
    "guarantees the emotion",
    "proven to cause",
)


class RuleKind(str, Enum):
    RULE = "rule"
    EXCEPTION = "exception"
    ANTI_RULE = "anti_rule"


@dataclass(frozen=True, slots=True)
class PaletteSwatch:
    hex_color: str
    name: str
    role: str

    def to_dict(self) -> dict[str, Any]:
        return {"hex_color": self.hex_color, "name": self.name, "role": self.role}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PaletteSwatch:
        return cls(
            hex_color=str(data["hex_color"]),
            name=str(data["name"]),
            role=str(data["role"]),
        )


@dataclass(frozen=True, slots=True)
class LanguageRule:
    id: str
    kind: RuleKind
    dimension: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "dimension": self.dimension,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LanguageRule:
        return cls(
            id=str(data["id"]),
            kind=RuleKind(str(data["kind"])),
            dimension=str(data["dimension"]),
            text=str(data["text"]),
        )


@dataclass(frozen=True, slots=True)
class EvolutionStep:
    id: str
    at: str
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "at": self.at, "note": self.note}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionStep:
        return cls(id=str(data["id"]), at=str(data["at"]), note=str(data["note"]))


@dataclass(frozen=True, slots=True)
class SafetyReview:
    skin_tone_safe: bool
    accessibility_ok: bool
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "skin_tone_safe": self.skin_tone_safe,
            "accessibility_ok": self.accessibility_ok,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SafetyReview:
        return cls(
            skin_tone_safe=bool(data["skin_tone_safe"]),
            accessibility_ok=bool(data["accessibility_ok"]),
            notes=str(data.get("notes", "")),
        )


@dataclass(frozen=True, slots=True)
class ShotColorProposal:
    id: str
    language_id: str
    shot_id: str
    color_intent: str
    accepted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "language_id": self.language_id,
            "shot_id": self.shot_id,
            "color_intent": self.color_intent,
            "accepted": self.accepted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShotColorProposal:
        return cls(
            id=str(data["id"]),
            language_id=str(data["language_id"]),
            shot_id=str(data["shot_id"]),
            color_intent=str(data["color_intent"]),
            accepted=bool(data.get("accepted", False)),
        )


@dataclass(frozen=True, slots=True)
class VisualLanguage:
    id: str
    project_id: str
    contrast: str
    saturation: str
    temperature: str
    source_motivation: str
    lighting_ratio: str
    production_design: str
    wardrobe: str
    skin_tone_rendering: str
    lens_render_interaction: str
    composition: str
    temporal_progression: str
    palette: tuple[PaletteSwatch, ...]
    rules: tuple[LanguageRule, ...]
    evolution: tuple[EvolutionStep, ...]
    reference_source_ids: tuple[str, ...]
    safety: SafetyReview
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "contrast": self.contrast,
            "saturation": self.saturation,
            "temperature": self.temperature,
            "source_motivation": self.source_motivation,
            "lighting_ratio": self.lighting_ratio,
            "production_design": self.production_design,
            "wardrobe": self.wardrobe,
            "skin_tone_rendering": self.skin_tone_rendering,
            "lens_render_interaction": self.lens_render_interaction,
            "composition": self.composition,
            "temporal_progression": self.temporal_progression,
            "palette": [item.to_dict() for item in self.palette],
            "rules": [item.to_dict() for item in self.rules],
            "evolution": [item.to_dict() for item in self.evolution],
            "reference_source_ids": list(self.reference_source_ids),
            "safety": self.safety.to_dict(),
            "disclaimer": self.disclaimer,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VisualLanguage:
        return cls(
            id=str(data["id"]),
            project_id=str(data["project_id"]),
            contrast=str(data["contrast"]),
            saturation=str(data["saturation"]),
            temperature=str(data["temperature"]),
            source_motivation=str(data["source_motivation"]),
            lighting_ratio=str(data["lighting_ratio"]),
            production_design=str(data["production_design"]),
            wardrobe=str(data["wardrobe"]),
            skin_tone_rendering=str(data["skin_tone_rendering"]),
            lens_render_interaction=str(data["lens_render_interaction"]),
            composition=str(data["composition"]),
            temporal_progression=str(data["temporal_progression"]),
            palette=tuple(PaletteSwatch.from_dict(item) for item in data.get("palette", ())),
            rules=tuple(LanguageRule.from_dict(item) for item in data.get("rules", ())),
            evolution=tuple(
                EvolutionStep.from_dict(item) for item in data.get("evolution", ())
            ),
            reference_source_ids=tuple(
                str(item) for item in data.get("reference_source_ids", ())
            ),
            safety=SafetyReview.from_dict(data["safety"]),
            disclaimer=str(data.get("disclaimer", DISCLAIMER)),
        )
