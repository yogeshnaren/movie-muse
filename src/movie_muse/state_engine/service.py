"""Permissioned deterministic state engine over FilmIR scene order."""

from __future__ import annotations

from typing import Any

from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.identity.api import Principal
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.schemas.api import (
    EpistemicLevel,
    FilmIR,
    InferredClaim,
    ScreenplayDocument,
    new_ulid,
)
from movie_muse.state_engine.errors import UnknownSceneError
from movie_muse.state_engine.extract import (
    extract_structural_transitions,
    transitions_from_inferred,
)
from movie_muse.state_engine.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.state_engine.reduce import facts_at_scene, reduce_transitions
from movie_muse.state_engine.types import (
    HumanCorrection,
    Reduction,
    StateDimension,
    StateFact,
    StateSnapshot,
    StateTransition,
)


class StateEngine:
    """Reduce character knowledge deterministically. No model calls."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization

    def reduce(
        self,
        film_ir: FilmIR,
        document: ScreenplayDocument,
        *,
        principal: Principal,
        acl_epoch: int,
        extra_transitions: tuple[StateTransition, ...] = (),
        inferred_claims: tuple[InferredClaim, ...] = (),
        inferred_scene_id: str | None = None,
        inferred_subject_id: str | None = None,
        persist: bool = True,
    ) -> Reduction:
        self._require(principal, Action.READ, document.project_id, acl_epoch)
        structural = extract_structural_transitions(film_ir, document)
        inferred: tuple[StateTransition, ...] = ()
        if inferred_claims:
            scene_id = inferred_scene_id or (film_ir.scene_order[0] if film_ir.scene_order else "")
            subject_id = inferred_subject_id or film_ir.id
            inferred = transitions_from_inferred(
                inferred_claims,
                scene_id=scene_id,
                subject_id=subject_id,
                dimension=StateDimension.KNOWLEDGE,
            )
        corrections = tuple(item.transition for item in self.list_corrections())
        merged = (*structural, *inferred, *extra_transitions, *corrections)
        reduction = reduce_transitions(film_ir, merged)
        if persist:
            self._persist_reduction(reduction)
        return reduction

    def query(
        self,
        film_ir: FilmIR,
        reduction: Reduction,
        *,
        scene_id: str,
        subject_id: str | None = None,
        dimension: StateDimension | None = None,
    ) -> StateSnapshot:
        if scene_id not in film_ir.scene_order:
            raise UnknownSceneError(f"unknown scene: {scene_id}")
        facts = facts_at_scene(reduction.facts, scene_id, film_ir)
        if subject_id is not None:
            facts = tuple(fact for fact in facts if fact.subject_id == subject_id)
        if dimension is not None:
            facts = tuple(fact for fact in facts if fact.dimension is dimension)
        return StateSnapshot(
            scene_id=scene_id,
            revision_id=reduction.revision_id,
            facts=facts,
        )

    def query_second_order(
        self,
        film_ir: FilmIR,
        reduction: Reduction,
        *,
        scene_id: str,
        subject_id: str,
        about_subject_id: str,
    ) -> tuple[StateFact, ...]:
        snapshot = self.query(
            film_ir,
            reduction,
            scene_id=scene_id,
            subject_id=subject_id,
            dimension=StateDimension.SECOND_ORDER_BELIEF,
        )
        return tuple(
            fact for fact in snapshot.facts if fact.about_subject_id == about_subject_id
        )

    def correct(
        self,
        transition: StateTransition,
        *,
        principal: Principal,
        acl_epoch: int,
        project_id: str,
    ) -> HumanCorrection:
        self._require(principal, Action.ACCEPT, project_id, acl_epoch)
        if transition.source_kind is not EpistemicLevel.AUTHORED:
            authored = StateTransition(
                subject_id=transition.subject_id,
                dimension=transition.dimension,
                attribute=transition.attribute,
                value=transition.value,
                polarity=transition.polarity,
                scene_id=transition.scene_id,
                source_kind=EpistemicLevel.AUTHORED,
                source_id=transition.source_id,
                evidence_ids=transition.evidence_ids,
                about_subject_id=transition.about_subject_id,
                subject_name=transition.subject_name,
            )
        else:
            authored = transition
        correction = HumanCorrection(
            id=f"stcor_{new_ulid()}",
            transition=authored,
            actor_id=principal.actor_id,
            created_at=utc_now(),
        )

        def persist(index: dict[str, Any]) -> HumanCorrection:
            digest = put_payload(self.workspace, correction.to_dict())
            index["correction_ids"] = [*list(index["correction_ids"]), correction.id]
            digests = dict(index["correction_digests"])
            digests[correction.id] = digest
            index["correction_digests"] = digests
            return correction

        return mutate_index(self.workspace, persist)

    def list_corrections(self) -> tuple[HumanCorrection, ...]:
        index = load_index(self.workspace)
        return tuple(
            HumanCorrection.from_dict(
                load_payload(self.workspace, str(index["correction_digests"][item_id]))
            )
            for item_id in index["correction_ids"]
        )

    def _persist_reduction(self, reduction: Reduction) -> None:
        def persist(index: dict[str, Any]) -> None:
            digest = put_payload(self.workspace, reduction.to_dict())
            by_revision = dict(index["reduction_by_revision"])
            by_revision[reduction.revision_id] = digest
            index["reduction_by_revision"] = by_revision
            digests = dict(index["reduction_digests"])
            digests[reduction.revision_id] = digest
            index["reduction_digests"] = digests

        mutate_index(self.workspace, persist)

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )
