"""Deterministic candidate transitions from FilmIR and the screenplay."""

from __future__ import annotations

from movie_muse.schemas.api import (
    BlockKind,
    EpistemicLevel,
    FilmIR,
    FilmIrEntityKind,
    InferredClaim,
    ScreenplayDocument,
)
from movie_muse.state_engine.types import Polarity, StateDimension, StateTransition


def extract_structural_transitions(
    film_ir: FilmIR,
    document: ScreenplayDocument,
) -> tuple[StateTransition, ...]:
    """Scene membership and location are structural. No model is called."""

    characters = {
        entity.id: entity
        for entity in film_ir.entities
        if entity.kind is FilmIrEntityKind.CHARACTER
    }
    locations = [
        entity
        for entity in film_ir.entities
        if entity.kind is FilmIrEntityKind.LOCATION
    ]
    scene_location: dict[str, tuple[str, str]] = {}
    for location in locations:
        for scene_id in location.scene_ids:
            scene_location[scene_id] = (location.id, location.canonical_name)

    heading_by_scene = {
        block.scene_id: block.id
        for block in document.blocks
        if block.kind is BlockKind.SCENE_HEADING and block.scene_id
    }
    transitions: list[StateTransition] = []
    for character in characters.values():
        for scene_id in character.scene_ids:
            loc = scene_location.get(scene_id)
            if loc is None:
                continue
            location_id, location_name = loc
            evidence = (heading_by_scene.get(scene_id, location_id), character.id)
            transitions.append(
                StateTransition(
                    subject_id=character.id,
                    subject_name=character.canonical_name,
                    dimension=StateDimension.LOCATION,
                    attribute="location",
                    value=location_name,
                    polarity=Polarity.CONFIRMED,
                    scene_id=scene_id,
                    source_kind=EpistemicLevel.STRUCTURAL,
                    source_id=film_ir.id,
                    evidence_ids=evidence,
                )
            )
    for scene_id in film_ir.scene_order:
        loc = scene_location.get(scene_id)
        if loc is None:
            continue
        transitions.append(
            StateTransition(
                subject_id=film_ir.id,
                subject_name="world",
                dimension=StateDimension.WORLD,
                attribute="active_location",
                value=loc[1],
                polarity=Polarity.CONFIRMED,
                scene_id=scene_id,
                source_kind=EpistemicLevel.STRUCTURAL,
                source_id=film_ir.id,
                evidence_ids=(heading_by_scene.get(scene_id, loc[0]),),
            )
        )
    return tuple(transitions)


def transitions_from_inferred(
    claims: tuple[InferredClaim, ...],
    *,
    scene_id: str,
    subject_id: str,
    dimension: StateDimension,
) -> tuple[StateTransition, ...]:
    """Wrap inferred claims as lowest-authority candidates. Never authored."""

    return tuple(
        StateTransition(
            subject_id=subject_id,
            dimension=dimension,
            attribute=claim.attribute,
            value=str(claim.value),
            polarity=Polarity.BELIEVES,
            scene_id=scene_id,
            source_kind=EpistemicLevel.INFERRED,
            source_id=claim.id,
            evidence_ids=(claim.evidence_bundle_id,),
        )
        for claim in claims
        if claim.kind is EpistemicLevel.INFERRED
    )
