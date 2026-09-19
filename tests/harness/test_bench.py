"""MovieMuse Bench: configuration identity and separated evaluation families."""

from __future__ import annotations

import pytest

from movie_muse.testkit.api import (
    BenchError,
    BenchRegistry,
    DecodingSettings,
    EvaluationFamily,
    TaskConfiguration,
    UniversalScoreForbiddenError,
    configuration_identity,
)


def test_configuration_identity_is_not_model_brand() -> None:
    shared_model = "local-extract-v1"
    decoding = DecodingSettings(temperature=0.0, top_p=1.0, seed=0)
    first = TaskConfiguration(
        model=shared_model,
        prompt="extract_scenes.v1",
        context_strategy="current_revision_only",
        tools=("schema_validate",),
        decoding=decoding,
        schema="structural_fact",
    )
    second = TaskConfiguration(
        model=shared_model,
        prompt="extract_scenes.v2_longer_context",
        context_strategy="revision_plus_notes",
        tools=("schema_validate", "rights_filter"),
        decoding=first.decoding,
        schema="structural_fact",
    )
    assert first.model == second.model
    assert configuration_identity(first) != configuration_identity(second)
    registry = BenchRegistry()
    with pytest.raises(BenchError, match="cannot rank by model brand"):
        registry.rank_by_model_brand()


def test_three_families_cannot_collapse_to_one_score() -> None:
    registry = BenchRegistry()
    assert registry.families() == frozenset(EvaluationFamily)
    objective = registry.score_objective("extract_scenes_small", matches=3, total=3)
    preference = registry.score_preference("blinded_rewrite_preference")
    utility = registry.score_utility("observed_scene_authoring_utility", observed_value=0.8)
    assert objective.family is EvaluationFamily.OBJECTIVE_GROUND_TRUTH
    assert preference.family is EvaluationFamily.BLINDED_HUMAN_PREFERENCE
    assert utility.family is EvaluationFamily.OBSERVED_WORKFLOW_UTILITY
    assert preference.method == "blinded_human_pairwise"
    assert "not_model_brand_ranking" in preference.assumptions
    assert any("hypotheses" in item.lower() for item in utility.assumptions)
    with pytest.raises(UniversalScoreForbiddenError, match="MovieMuseScore"):
        registry.report(objective, preference, utility).collapse_to_universal_score()
    with pytest.raises(UniversalScoreForbiddenError):
        registry.collapse_to_universal_score(registry.report(objective))
    assert not hasattr(registry, "movie_muse_score")
