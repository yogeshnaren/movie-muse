"""Every major domain schema has a committed valid and invalid fixture.

Acceptance criterion 5 for MM-002: "Valid and invalid fixtures for each major
schema." This test loads ``tests/schemas/fixtures/<schema_name>/{valid,invalid}.json``
for every schema registered under ``schemas/domain`` (excluding the shared
``common`` defs document, which is not itself a payload schema) and proves the
valid fixture validates while the invalid fixture is rejected.

Fixtures live under ``tests/schemas/fixtures`` rather than a top-level
``fixtures/schemas`` directory so they stay inside the ``domain.schemas``
verification scope (``config/verification-scopes.yaml`` owns
``tests/schemas/**`` for MM-002) and are covered by MM-002's input
fingerprint without editing the scope catalog itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

from movie_muse.schemas import validators

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"


SCHEMA_NAMES = [
    path.name[: -len(".schema.json")]
    for path in sorted(validators.domain_schema_dir(REPO_ROOT).glob("*.schema.json"))
    if path.name != "common.schema.json"
]


def test_every_domain_schema_has_a_fixture_directory() -> None:
    missing = [name for name in SCHEMA_NAMES if not (FIXTURES_ROOT / name).is_dir()]
    assert missing == [], f"missing fixture directories: {missing}"


@pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
def test_valid_fixture_validates(schema_name: str) -> None:
    payload = json.loads((FIXTURES_ROOT / schema_name / "valid.json").read_text(encoding="utf-8"))
    validators.validate_payload(schema_name, payload)


@pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
def test_invalid_fixture_is_rejected(schema_name: str) -> None:
    payload = json.loads((FIXTURES_ROOT / schema_name / "invalid.json").read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        validators.validate_payload(schema_name, payload)


def test_schema_names_cover_every_acceptance_listed_domain_type() -> None:
    required_types = {
        "project",
        "screenplay_document",
        "film_ir",
        "creative_intent_ir",
        "project_memory",
        "proposal",
        "change_set",
        "project_event",
        "evidence_bundle",
        "rights_record",
        "collaboration_event",
        "shot_ir",
        "scene_space",
        "production_projection",
        "scenario_model",
        "artifact",
        "artifact_version",
        "dependency_node",
        "epistemic_authored_fact",
        "epistemic_structural_fact",
        "epistemic_inferred_claim",
        "epistemic_operational_assumption",
        "epistemic_scenario_output",
    }
    missing = required_types - set(SCHEMA_NAMES)
    assert missing == set()
