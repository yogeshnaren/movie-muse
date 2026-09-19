"""Bench registry, local/fine-tuned baselines, and Creator Leverage."""

from __future__ import annotations

import pytest

from movie_muse.evaluation.api import (
    LeverageError,
    PopulationClaimError,
    assert_no_population_claim,
)
from movie_muse.security.api import ControlPlane
from movie_muse.toolchain.paths import repo_root


def test_bench_loads_existing_fixture_tasks(plane: ControlPlane) -> None:
    tasks = {task.id: task for task in plane.evaluation.tasks()}
    assert "extract_scenes_small" in tasks
    assert "blinded_rewrite_preference" in tasks
    assert "observed_scene_authoring_utility" in tasks


def test_local_and_fine_tuned_routes_meet_baselines(plane: ControlPlane) -> None:
    local = plane.evaluation.evaluate_route(
        kind="local",
        task_id="extract_scenes_small",
        principal=plane.principal,
        acl_epoch=plane.epoch,
    )
    tuned = plane.evaluation.evaluate_route(
        kind="fine_tuned",
        task_id="extract_scenes_small",
        principal=plane.principal,
        acl_epoch=plane.epoch,
    )
    assert local.id.startswith("evl_")
    assert local.route_kind == "local"
    assert local.quality >= 0.7
    assert local.safety == 1.0
    assert tuned.route_kind == "fine_tuned"
    assert tuned.provider == "finetune_script_adapter"


def test_correction_burden_and_positive_leverage(plane: ControlPlane) -> None:
    burden = plane.evaluation.correction_burden(
        regenerations=2, accepted=4, correction_minutes=6.0
    )
    assert burden.ratio == 0.5
    leverage = plane.evaluation.creator_leverage(
        useful_minutes_removed=20.0,
        correction_minutes=4.0,
        verification_minutes=4.0,
    )
    assert leverage.ratio == 2.5
    with pytest.raises(LeverageError):
        plane.evaluation.creator_leverage(
            useful_minutes_removed=3.0,
            correction_minutes=2.0,
            verification_minutes=2.0,
        )


def test_synthetic_output_is_not_a_population_sample(plane: ControlPlane) -> None:
    labeled = (
        "Synthetic audiences are hypotheses, not human samples. "
        "This is not a human sample and not a demographic population estimate."
    )
    assert_no_population_claim(labeled)
    plane.evaluation.assert_advisory_label(labeled)
    with pytest.raises(PopulationClaimError):
        assert_no_population_claim("this is a human sample of the audience")


@pytest.mark.architecture
def test_evaluation_package_imports_only_public_sibling_apis() -> None:
    package = repo_root() / "src" / "movie_muse" / "evaluation"
    siblings = (
        "audit",
        "authorization",
        "identity",
        "model_router",
        "persistence",
        "retrieval",
        "schemas",
        "testkit",
    )
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for sibling in siblings:
            private_prefix = f"from movie_muse.{sibling}."
            public_import = f"from movie_muse.{sibling}.api import"
            assert private_prefix not in text.replace(public_import, "")
        assert "from tests." not in text
