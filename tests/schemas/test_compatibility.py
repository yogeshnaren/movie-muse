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


def test_narrowing_an_existing_enum_is_breaking() -> None:
    old_schema = {
        "type": "object",
        "required": ["status"],
        "properties": {"status": {"type": "string", "enum": ["draft", "approved"]}},
    }
    new_schema = {
        "type": "object",
        "required": ["status"],
        "properties": {"status": {"type": "string", "enum": ["draft"]}},
    }
    assert classify_schema_change(old_schema, new_schema) is CompatibilityKind.BREAKING


def test_widening_an_existing_enum_is_conservatively_breaking() -> None:
    old_schema = {
        "type": "object",
        "required": ["status"],
        "properties": {"status": {"type": "string", "enum": ["draft"]}},
    }
    new_schema = {
        "type": "object",
        "required": ["status"],
        "properties": {"status": {"type": "string", "enum": ["draft", "approved"]}},
    }
    assert classify_schema_change(old_schema, new_schema) is CompatibilityKind.BREAKING


def test_reordering_an_enum_is_additive() -> None:
    old_schema = {
        "type": "object",
        "required": ["status"],
        "properties": {"status": {"type": "string", "enum": ["draft", "approved"]}},
    }
    new_schema = {
        "type": "object",
        "required": ["status"],
        "properties": {"status": {"type": "string", "enum": ["approved", "draft"]}},
    }
    assert classify_schema_change(old_schema, new_schema) is CompatibilityKind.ADDITIVE


def test_changing_const_ref_pattern_or_bounds_is_breaking() -> None:
    base = {
        "type": "object",
        "required": ["code"],
        "properties": {"code": {"type": "string", "const": "A", "pattern": "^A$", "minLength": 1}},
    }
    for mutated in (
        {**base, "properties": {"code": {"type": "string", "const": "B", "pattern": "^A$", "minLength": 1}}},
        {**base, "properties": {"code": {"$ref": "#/$defs/code"}}},
        {**base, "properties": {"code": {"type": "string", "const": "A", "pattern": "^B$", "minLength": 1}}},
        {**base, "properties": {"code": {"type": "string", "const": "A", "pattern": "^A$", "minLength": 2}}},
    ):
        assert classify_schema_change(base, mutated) is CompatibilityKind.BREAKING


def test_nested_object_constraint_change_is_breaking() -> None:
    old_schema = {
        "type": "object",
        "required": ["payload"],
        "properties": {
            "payload": {
                "type": "object",
                "properties": {"flag": {"type": "string", "enum": ["on", "off"]}},
            }
        },
    }
    new_schema = {
        "type": "object",
        "required": ["payload"],
        "properties": {
            "payload": {
                "type": "object",
                "properties": {"flag": {"type": "string", "enum": ["on"]}},
            }
        },
    }
    assert classify_schema_change(old_schema, new_schema) is CompatibilityKind.BREAKING


def test_annotation_only_change_is_additive() -> None:
    new_schema = {
        "type": "object",
        "description": "a project name",
        "required": ["id", "name"],
        "properties": {
            "id": {"type": "string", "title": "Identifier"},
            "name": {"type": "string"},
        },
    }
    assert classify_schema_change(BASE, new_schema) is CompatibilityKind.ADDITIVE


def test_changing_existing_defs_is_breaking_but_adding_defs_is_additive() -> None:
    old_schema = {
        "type": "object",
        "required": ["code"],
        "properties": {"code": {"$ref": "#/$defs/code"}},
        "$defs": {"code": {"type": "string", "enum": ["A", "B"]}},
    }
    narrowed_defs = {
        "type": "object",
        "required": ["code"],
        "properties": {"code": {"$ref": "#/$defs/code"}},
        "$defs": {"code": {"type": "string", "enum": ["A"]}},
    }
    extra_defs = {
        "type": "object",
        "required": ["code"],
        "properties": {"code": {"$ref": "#/$defs/code"}},
        "$defs": {
            "code": {"type": "string", "enum": ["A", "B"]},
            "unused": {"type": "string"},
        },
    }
    assert classify_schema_change(old_schema, narrowed_defs) is CompatibilityKind.BREAKING
    assert classify_schema_change(old_schema, extra_defs) is CompatibilityKind.ADDITIVE


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
