"""Epistemic-level state cannot be silently promoted or interchanged.

Runtime half of the proof required by MM-002 acceptance criterion 2. The
static half (mypy rejects cross-kind assignment) lives in
``tests/schemas/test_typecheck_fixtures.py``.
"""

from __future__ import annotations

from typing import Any

import pytest
from jsonschema.exceptions import ValidationError

from movie_muse.schemas import validators
from movie_muse.schemas.epistemic import (
    AuthoredFact,
    InferredClaim,
    OperationalAssumption,
    ScenarioOutput,
    StructuralFact,
)

INSTANCES_BY_LEVEL: dict[str, Any] = {
    "authored_fact": AuthoredFact(
        id="fca_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        subject_id="char-ada",
        attribute="occupation",
        value="locksmith",
        source_revision_id="rev_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        author_actor_id="act_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    ),
    "structural_fact": StructuralFact(
        id="fcs_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        subject_id="char-ada",
        attribute="scene_count",
        value=12,
        derived_from_revision_id="rev_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        extractor_version="1.0.0",
    ),
    "inferred_claim": InferredClaim(
        id="cli_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        subject_id="char-ada",
        attribute="motive",
        value="protect her sister",
        confidence=0.6,
        evidence_bundle_id="evb_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        model_id="semantic-claims-v1",
    ),
    "operational_assumption": OperationalAssumption(
        id="aso_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        subject_id="scn_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        attribute="shoot_days",
        value=1.5,
        assumed_by_actor_id="act_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    ),
    "scenario_output": ScenarioOutput(
        id="osc_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        subject_id="proj_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        attribute="opening_weekend_revenue",
        value=4_000_000,
        scenario_model_id="scm_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    ),
}

LEVELS = sorted(INSTANCES_BY_LEVEL)


@pytest.mark.parametrize("level", LEVELS)
def test_own_schema_accepts_its_own_instance(level: str) -> None:
    schema_name = f"epistemic_{level}"
    payload = INSTANCES_BY_LEVEL[level].to_dict()
    validators.validate_payload(schema_name, payload)


EXPECTED_KIND_VALUE = {
    "authored_fact": "authored",
    "structural_fact": "structural",
    "inferred_claim": "inferred",
    "operational_assumption": "operational",
    "scenario_output": "scenario",
}


@pytest.mark.parametrize("level", LEVELS)
def test_own_dataclass_kind_matches_schema_name(level: str) -> None:
    instance = INSTANCES_BY_LEVEL[level]
    assert instance.kind.value == EXPECTED_KIND_VALUE[level]


@pytest.mark.parametrize(
    ("source_level", "target_level"),
    [(source, target) for source in LEVELS for target in LEVELS if source != target],
)
def test_cross_kind_payload_validation_fails(source_level: str, target_level: str) -> None:
    """Validating one epistemic level's serialized payload against a different
    level's schema must fail: the ``kind`` const mismatches and/or the
    level-specific provenance fields required by the target schema are absent.
    """

    payload = INSTANCES_BY_LEVEL[source_level].to_dict()
    target_schema_name = f"epistemic_{target_level}"
    with pytest.raises(ValidationError):
        validators.validate_payload(target_schema_name, payload)


def test_inferred_claim_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError):
        InferredClaim(
            id="cli_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            subject_id="char-ada",
            attribute="motive",
            value="x",
            confidence=1.4,
            evidence_bundle_id="evb_01ARZ3NDEKTSV4RRFFQ69G5FAV",
            model_id="m",
        )


def test_epistemic_types_are_nominally_distinct_python_classes() -> None:
    """None of the five epistemic dataclasses inherits from another, so mypy
    (see the typecheck fixtures test) treats them as unrelated types even
    though this test shows they are structurally similar at runtime.
    """

    types_ = [type(instance) for instance in INSTANCES_BY_LEVEL.values()]
    for i, type_a in enumerate(types_):
        for type_b in types_[i + 1 :]:
            assert type_a is not type_b
            assert not issubclass(type_a, type_b)
            assert not issubclass(type_b, type_a)
