"""ProjectEvent: immutable command -> event history with an integrity hash."""

from __future__ import annotations

import pytest

from movie_muse.schemas import ids, validators
from movie_muse.schemas.events import EVENT_TYPES, ProjectEvent, compute_integrity_hash


def _make_event(**overrides: object) -> ProjectEvent:
    kwargs: dict[str, object] = {
        "id": ids.new_id("event"),
        "project_id": ids.new_id("project"),
        "branch_id": ids.new_id("branch"),
        "result_revision_id": ids.new_id("revision"),
        "actor_id": ids.new_id("actor"),
        "effective_principal_id": ids.new_id("actor"),
        "command_id": "cmd-move-scene",
        "operation_id": "op-1",
        "event_type": "SceneMoved",
        "created_at": "2026-09-01T00:00:00Z",
        "correlation_id": "corr-1",
        "base_revision_id": None,
        "causal_id": None,
        "payload": {"scene_id": "scn_x"},
    }
    kwargs.update(overrides)
    integrity_hash = compute_integrity_hash(
        project_id=kwargs["project_id"],
        branch_id=kwargs["branch_id"],
        base_revision_id=kwargs["base_revision_id"],
        result_revision_id=kwargs["result_revision_id"],
        actor_id=kwargs["actor_id"],
        effective_principal_id=kwargs["effective_principal_id"],
        command_id=kwargs["command_id"],
        operation_id=kwargs["operation_id"],
        event_type=kwargs["event_type"],
        schema_version="1.0",
        causal_id=kwargs["causal_id"],
        correlation_id=kwargs["correlation_id"],
        payload=kwargs["payload"] or {},
    )
    kwargs.setdefault("integrity_hash", overrides.get("integrity_hash", integrity_hash))
    return ProjectEvent(**kwargs)  # type: ignore[arg-type]


def test_event_types_cover_the_architecture_named_examples() -> None:
    named = {
        "ScreenplayPatchAccepted",
        "CharacterIntentLocked",
        "SceneMoved",
        "ProductionRequirementConfirmed",
        "DepartmentDecisionConfirmed",
        "AssumptionChanged",
    }
    assert named == EVENT_TYPES


def test_valid_event_passes_schema_validation() -> None:
    event = _make_event()
    validators.validate_payload("project_event", event.to_dict())


def test_round_trip_preserves_fields() -> None:
    event = _make_event()
    restored = ProjectEvent.from_dict(event.to_dict())
    assert restored == event


def test_unknown_event_type_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown event_type"):
        _make_event(event_type="SomethingMadeUp")


def test_tampered_integrity_hash_is_rejected() -> None:
    with pytest.raises(ValueError, match="integrity_hash"):
        _make_event(integrity_hash="0" * 64)


def test_event_payload_is_recursively_immutable() -> None:
    event = _make_event(payload={"value": "before"})
    with pytest.raises(TypeError):
        event.payload["value"] = "after"  # type: ignore[index]


def test_tampered_payload_after_hash_computation_is_rejected() -> None:
    event = _make_event()
    tampered = event.to_dict()
    tampered["payload"] = {"scene_id": "scn_a_different_scene"}
    with pytest.raises(ValueError, match="integrity_hash"):
        ProjectEvent.from_dict(tampered)


def test_integrity_hash_is_deterministic_for_identical_inputs() -> None:
    common = {
        "project_id": ids.new_id("project"),
        "branch_id": ids.new_id("branch"),
        "base_revision_id": None,
        "result_revision_id": ids.new_id("revision"),
        "actor_id": ids.new_id("actor"),
        "effective_principal_id": ids.new_id("actor"),
        "command_id": "cmd-1",
        "operation_id": "op-1",
        "event_type": "AssumptionChanged",
        "schema_version": "1.0",
        "causal_id": None,
        "correlation_id": "corr-1",
        "payload": {"a": 1, "b": 2},
    }
    assert compute_integrity_hash(**common) == compute_integrity_hash(**common)
