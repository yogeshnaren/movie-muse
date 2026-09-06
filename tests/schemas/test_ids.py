"""Stable ID rules: prefixes, ULID shape, sortability, and kind validation."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from movie_muse.schemas import ids

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMON_SCHEMA_PATH = REPO_ROOT / "schemas" / "domain" / "common.schema.json"

#: entity kind -> the $defs key used in common.schema.json (camelCase Id names).
KIND_TO_DEFS_KEY = {
    "document": "documentId",
    "sequence": "sequenceId",
    "block": "blockId",
    "inline_span": "inlineSpanId",
    "scene": "sceneId",
    "character_cue": "characterCueId",
    "dialogue_pair": "dialoguePairId",
    "note": "noteId",
    "revision_mark": "revisionMarkId",
    "production_tag": "productionTagId",
    "attachment": "attachmentId",
    "project": "projectId",
    "revision": "revisionId",
    "branch": "branchId",
    "actor": "actorId",
    "event": "eventId",
    "change_set": "changeSetId",
    "proposal": "proposalId",
    "evidence_bundle": "evidenceBundleId",
    "rights_record": "rightsRecordId",
    "collaboration_event": "collaborationEventId",
    "shot": "shotId",
    "scene_space": "sceneSpaceId",
    "production_projection": "productionProjectionId",
    "scenario_model": "scenarioModelId",
    "artifact": "artifactId",
    "artifact_version": "artifactVersionId",
    "dependency_node": "dependencyNodeId",
    "project_memory": "projectMemoryId",
    "film_ir": "filmIrId",
    "creative_intent": "creativeIntentId",
    "authored_fact": "authoredFactId",
    "structural_fact": "structuralFactId",
    "inferred_claim": "inferredClaimId",
    "operational_assumption": "operationalAssumptionId",
    "scenario_output": "scenarioOutputId",
}


def test_every_id_kind_has_a_defs_mapping() -> None:
    assert set(KIND_TO_DEFS_KEY) == set(ids.ID_KIND_PREFIXES)


def test_common_schema_patterns_match_the_python_prefix_table() -> None:
    common = json.loads(COMMON_SCHEMA_PATH.read_text(encoding="utf-8"))
    defs = common["$defs"]
    for kind in ids.ID_KIND_PREFIXES:
        defs_key = KIND_TO_DEFS_KEY[kind]
        schema_pattern = defs[defs_key]["pattern"]
        expected = ids.ID_PATTERNS[kind].pattern
        assert schema_pattern == expected, f"{kind}: schema pattern {schema_pattern!r} != {expected!r}"


@pytest.mark.parametrize("kind", sorted(ids.ID_KIND_PREFIXES))
def test_new_id_is_valid_and_parses_back_to_its_kind(kind: str) -> None:
    value = ids.new_id(kind)
    assert ids.is_valid_id(kind, value)
    assert ids.parse_id_kind(value) == kind
    assert ids.require_id(kind, value) == value


def test_new_id_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError):
        ids.new_id("not_a_real_kind")


def test_is_valid_id_rejects_cross_kind_values() -> None:
    scene_id = ids.new_id("scene")
    assert ids.is_valid_id("scene", scene_id)
    assert not ids.is_valid_id("block", scene_id)


def test_parse_id_kind_rejects_malformed_values() -> None:
    with pytest.raises(ValueError):
        ids.parse_id_kind("not-an-id")
    with pytest.raises(ValueError):
        ids.parse_id_kind("scn_tooshort")


def test_require_id_raises_with_field_name_context() -> None:
    with pytest.raises(ValueError, match="scene_id"):
        ids.require_id("scene", "blk_not-a-scene-id", field_name="scene_id")


def test_ulid_is_lexicographically_sortable_by_creation_time() -> None:
    earlier = ids.new_ulid(_time_ms=1_700_000_000_000, _random_bytes=bytes(10))
    later = ids.new_ulid(_time_ms=1_700_000_000_001, _random_bytes=bytes(10))
    assert earlier < later


def test_ulid_is_unique_across_many_calls() -> None:
    values = {ids.new_ulid() for _ in range(500)}
    assert len(values) == 500


def test_ulid_rejects_wrong_length_randomness() -> None:
    with pytest.raises(ValueError):
        ids.new_ulid(_random_bytes=b"short")


def test_ulid_matches_real_wall_clock_ordering() -> None:
    first = ids.new_ulid()
    time.sleep(0.002)
    second = ids.new_ulid()
    assert first < second
