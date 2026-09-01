"""Migration hooks: version field + migrate(from, to), with real registered steps."""

from __future__ import annotations

import pytest

from movie_muse.schemas import ids, validators
from movie_muse.schemas.migrations import (
    DEFAULT_REGISTRY,
    MigrationPathError,
    MigrationRegistry,
    SchemaMigration,
)


def test_rights_record_migrates_1_0_to_1_1_and_validates_against_current_schema() -> None:
    v1_0_payload = {
        "id": ids.new_id("rights_record"),
        "source_id": "src-1",
        "basis": "user_owned",
        "owner_actor_id": ids.new_id("actor"),
        "registered_at": "2026-01-01T00:00:00Z",
        "allow_training": False,
        "schema_version": "1.0",
    }
    assert "license_expiry" not in v1_0_payload

    migrated = DEFAULT_REGISTRY.migrate(
        "rights_record", v1_0_payload, from_version="1.0", to_version="1.1"
    )
    assert migrated["schema_version"] == "1.1"
    assert migrated["license_expiry"] is None
    validators.validate_payload("rights_record", migrated)


def test_collaboration_event_migrates_1_0_to_1_1() -> None:
    v1_0_payload = {
        "id": ids.new_id("collaboration_event"),
        "project_id": ids.new_id("project"),
        "source": "zoom-adapter",
        "record_kind": "idea",
        "summary": "what if the safe is already open",
        "captured_at": "2026-01-01T00:00:00Z",
        "promotion_state": "captured",
        "schema_version": "1.0",
    }
    migrated = DEFAULT_REGISTRY.migrate(
        "collaboration_event", v1_0_payload, from_version="1.0", to_version="1.1"
    )
    assert migrated["schema_version"] == "1.1"
    assert migrated["promoted_project_memory_id"] is None
    validators.validate_payload("collaboration_event", migrated)


def test_migrate_same_version_is_a_no_op_copy() -> None:
    payload = {"schema_version": "1.0", "value": 1}
    result = DEFAULT_REGISTRY.migrate("rights_record", payload, from_version="1.0", to_version="1.0")
    assert result == payload
    assert result is not payload


def test_unregistered_migration_path_fails_closed() -> None:
    with pytest.raises(MigrationPathError):
        DEFAULT_REGISTRY.migrate("rights_record", {"schema_version": "1.0"}, from_version="1.0", to_version="9.9")


def test_registering_a_duplicate_from_version_is_rejected() -> None:
    registry = MigrationRegistry()
    registry.register(
        SchemaMigration(schema_name="widget", from_version="1.0", to_version="1.1", upgrade=lambda p: dict(p))
    )
    with pytest.raises(ValueError, match="already registered"):
        registry.register(
            SchemaMigration(schema_name="widget", from_version="1.0", to_version="1.2", upgrade=lambda p: dict(p))
        )


def test_multi_step_migration_chain_is_walked_in_order() -> None:
    registry = MigrationRegistry()
    registry.register(
        SchemaMigration(
            schema_name="widget",
            from_version="1.0",
            to_version="1.1",
            upgrade=lambda p: {**p, "step_one": True},
        )
    )
    registry.register(
        SchemaMigration(
            schema_name="widget",
            from_version="1.1",
            to_version="1.2",
            upgrade=lambda p: {**p, "step_two": True},
        )
    )
    result = registry.migrate("widget", {"schema_version": "1.0"}, from_version="1.0", to_version="1.2")
    assert result["step_one"] is True
    assert result["step_two"] is True
    assert result["schema_version"] == "1.2"


def test_migration_cycle_is_detected() -> None:
    registry = MigrationRegistry()
    registry.register(
        SchemaMigration(schema_name="widget", from_version="1.0", to_version="1.1", upgrade=lambda p: dict(p))
    )
    registry.register(
        SchemaMigration(schema_name="widget", from_version="1.1", to_version="1.0", upgrade=lambda p: dict(p))
    )
    with pytest.raises(MigrationPathError, match="cycle"):
        registry.migrate("widget", {"schema_version": "1.0"}, from_version="1.0", to_version="9.9")
