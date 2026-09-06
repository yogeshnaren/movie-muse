"""MovieMuse Bench: task configurations scored per evaluation family.

Fine-tuning is out of scope. Families cannot collapse into one MovieMuseScore.
Preference records blinded human labels, never model-name-only ranking.
Synthetic audiences remain hypotheses.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from movie_muse.persistence.api import digest_payload
from movie_muse.provenance.api import SYNTHETIC_AUDIENCE_DISCLAIMER
from movie_muse.testkit.errors import BenchError, UniversalScoreForbiddenError
from movie_muse.testkit.paths import bench_root
from movie_muse.testkit.types import (
    BenchReport,
    BenchTask,
    BlindedPreferenceLabel,
    EvaluationFamily,
    FamilyScore,
    TaskConfiguration,
)


def configuration_identity(config: TaskConfiguration) -> str:
    _encoded, digest = digest_payload(config.to_dict())
    return digest


def _parse_task(raw: dict[str, Any]) -> BenchTask:
    family = EvaluationFamily(str(raw["family"]))
    configuration = TaskConfiguration.from_dict(dict(raw["configuration"]))
    labels = tuple(
        BlindedPreferenceLabel(
            rater_id=str(item["rater_id"]),
            winner_configuration_id=str(item["winner_configuration_id"]),
            loser_configuration_id=str(item["loser_configuration_id"]),
            blinded=bool(item.get("blinded", True)),
            notes=str(item.get("notes") or ""),
        )
        for item in (raw.get("labels") or ())
    )
    disclaimer = raw.get("disclaimer")
    return BenchTask(
        id=str(raw["id"]),
        family=family,
        configuration=configuration,
        fixture_id=str(raw["fixture_id"]) if raw.get("fixture_id") else None,
        labels=labels,
        utility_metric=str(raw["utility_metric"]) if raw.get("utility_metric") else None,
        disclaimer=str(disclaimer) if disclaimer is not None else None,
    )


class BenchRegistry:
    def __init__(self, root: Path | None = None) -> None:
        self.root = bench_root(root)
        self._tasks = self._load()

    def _load(self) -> dict[str, BenchTask]:
        path = self.root / "tasks.yaml"
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict) or not isinstance(loaded.get("tasks"), list):
            raise BenchError("bench/tasks.yaml must contain a tasks list")
        tasks = [_parse_task(dict(item)) for item in loaded["tasks"]]
        by_id = {task.id: task for task in tasks}
        if len(by_id) != len(tasks):
            raise BenchError("duplicate bench task ids")
        return by_id

    def tasks(self) -> tuple[BenchTask, ...]:
        return tuple(self._tasks[key] for key in sorted(self._tasks))

    def task(self, task_id: str) -> BenchTask:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise BenchError(f"unknown bench task {task_id}") from exc

    def families(self) -> frozenset[EvaluationFamily]:
        return frozenset(task.family for task in self._tasks.values())

    def score_objective(self, task_id: str, *, matches: int, total: int) -> FamilyScore:
        task = self.task(task_id)
        if task.family is not EvaluationFamily.OBJECTIVE_GROUND_TRUTH:
            raise BenchError(f"{task_id} is not an objective ground-truth task")
        if total <= 0:
            raise BenchError("objective scoring requires a positive total")
        identity = configuration_identity(task.configuration)
        return FamilyScore(
            family=task.family,
            value=matches / total,
            method="exact_structural_match",
            configuration_id=identity,
            assumptions=("ground_truth_from_document_kernel",),
            uncertainty="deterministic_fixture",
        )

    def score_preference(self, task_id: str) -> FamilyScore:
        task = self.task(task_id)
        if task.family is not EvaluationFamily.BLINDED_HUMAN_PREFERENCE:
            raise BenchError(f"{task_id} is not a blinded preference task")
        if not task.labels:
            raise BenchError("preference family requires blinded human labels")
        if any(not label.blinded for label in task.labels):
            raise BenchError("preference labels must be blinded")
        identity = configuration_identity(task.configuration)
        wins = sum(1 for label in task.labels if label.winner_configuration_id == identity)
        return FamilyScore(
            family=task.family,
            value=wins / len(task.labels),
            method="blinded_human_pairwise",
            configuration_id=identity,
            assumptions=("human_rater", "not_model_brand_ranking"),
            uncertainty="human_label_sample",
        )

    def score_utility(self, task_id: str, *, observed_value: float) -> FamilyScore:
        task = self.task(task_id)
        if task.family is not EvaluationFamily.OBSERVED_WORKFLOW_UTILITY:
            raise BenchError(f"{task_id} is not an observed workflow-utility task")
        identity = configuration_identity(task.configuration)
        return FamilyScore(
            family=task.family,
            value=float(observed_value),
            method=task.utility_metric or "observed_workflow",
            configuration_id=identity,
            assumptions=("observed_workflow", SYNTHETIC_AUDIENCE_DISCLAIMER),
            uncertainty="observed_not_guaranteed",
        )

    def report(self, *scores: FamilyScore) -> BenchReport:
        if not scores:
            raise BenchError("a bench report needs at least one family score")
        families = [score.family for score in scores]
        if len(families) != len(set(families)):
            raise BenchError("duplicate family scores cannot be averaged away")
        configuration_ids = {score.configuration_id for score in scores}
        if len(configuration_ids) != 1:
            raise BenchError("a report must describe one TaskConfiguration identity")
        return BenchReport(configuration_id=next(iter(configuration_ids)), scores=tuple(scores))

    def rank_by_model_brand(self) -> None:
        raise BenchError(
            "cannot rank by model brand; MovieMuse Bench scores TaskConfiguration identity"
        )

    def collapse_to_universal_score(self, report: BenchReport) -> float:
        del report
        raise UniversalScoreForbiddenError(
            "MovieMuse Bench cannot collapse evaluation families into one MovieMuseScore"
        )
