"""Compatibility policy: classify a schema change as additive or breaking."""

from __future__ import annotations

from movie_muse.schemas.compatibility import CompatibilityKind, classify_schema_change

BASE = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
    },
}


def test_adding_an_optional_property_is_additive() -> None:
    new_schema = {
        "type": "object",
        "required": ["id", "name"],
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "nickname": {"type": "string"},
        },
    }
    assert classify_schema_change(BASE, new_schema) is CompatibilityKind.ADDITIVE


def test_identical_schema_is_additive() -> None:
    assert classify_schema_change(BASE, dict(BASE)) is CompatibilityKind.ADDITIVE


def test_removing_a_required_property_is_breaking() -> None:
    new_schema = {
        "type": "object",
        "required": ["id"],
        "properties": {"id": {"type": "string"}},
    }
    assert classify_schema_change(BASE, new_schema) is CompatibilityKind.BREAKING


def test_adding_a_new_required_property_is_breaking() -> None:
    new_schema = {
        "type": "object",
        "required": ["id", "name", "owner_id"],
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "owner_id": {"type": "string"},
        },
    }
    assert classify_schema_change(BASE, new_schema) is CompatibilityKind.BREAKING


def test_changing_an_existing_propertys_type_is_breaking() -> None:
    new_schema = {
        "type": "object",
        "required": ["id", "name"],
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
        },
    }
    assert classify_schema_change(BASE, new_schema) is CompatibilityKind.BREAKING


def test_making_a_required_property_optional_is_conservatively_breaking() -> None:
    """The policy intentionally treats any required-ness change as breaking:
    a consumer relying on the old required guarantee should not silently
    start receiving payloads without it.
    """

    new_schema = {
        "type": "object",
        "required": ["id"],
        "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
        },
    }
    assert classify_schema_change(BASE, new_schema) is CompatibilityKind.BREAKING


def test_real_rights_record_evolution_is_additive() -> None:
    v1_0 = {
        "type": "object",
        "required": ["id", "source_id", "basis", "owner_actor_id", "registered_at", "allow_training", "schema_version"],
        "properties": {
            "id": {"type": "string"},
            "source_id": {"type": "string"},
            "basis": {"type": "string"},
            "owner_actor_id": {"type": "string"},
            "registered_at": {"type": "string"},
            "allow_training": {"type": "boolean"},
            "license_summary": {"type": ["string", "null"]},
            "schema_version": {"type": "string"},
        },
    }
    v1_1 = {
        "type": "object",
        "required": ["id", "source_id", "basis", "owner_actor_id", "registered_at", "allow_training", "schema_version"],
        "properties": {
            **v1_0["properties"],
            "license_expiry": {"type": ["string", "null"]},
        },
    }
    assert classify_schema_change(v1_0, v1_1) is CompatibilityKind.ADDITIVE
