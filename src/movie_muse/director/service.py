"""Deterministic DirectorVisionGraph: SceneSpace, coverage, constraints, annotations."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.dependencies.api import DependencyEngine, NodeKind
from movie_muse.director.errors import (
    AnnotationNotFoundError,
    ConstraintNotFoundError,
    CoverageNotFoundError,
    LockedGeometryError,
    SceneSpaceNotFoundError,
)
from movie_muse.director.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.director.types import (
    AnnotationRole,
    CoverageBeat,
    CoveragePurpose,
    DirectorVisionGraph,
    ProducerConstraint,
    RoleAnnotation,
    SceneSpaceRecord,
    SemanticAnchor,
)
from movie_muse.identity.api import Principal
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.schemas.api import SceneSpace, SubjectPosition, new_id, new_ulid


def _put_keyed(
    index: dict[str, Any],
    workspace: LocalWorkspace,
    *,
    ids_key: str,
    digests_key: str,
    item_id: str,
    payload: dict[str, Any],
) -> None:
    digest = put_payload(workspace, payload)
    ids = list(index[ids_key])
    if item_id not in ids:
        ids.append(item_id)
    index[ids_key] = ids
    digests = dict(index[digests_key])
    digests[item_id] = digest
    index[digests_key] = digests


class DirectorVisionService:
    """Provider-independent Director Mode. Generation is optional and never required."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        *,
        dependencies: DependencyEngine | None = None,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.dependencies = dependencies
        self.clock = clock

    def graph(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> DirectorVisionGraph:
        self._require(principal, Action.READ, project_id, acl_epoch)
        return self._graph(project_id)

    def set_generation_enabled(
        self,
        project_id: str,
        enabled: bool,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> DirectorVisionGraph:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        graph = self._graph(project_id)
        stored = self._put_graph(
            DirectorVisionGraph(
                project_id=project_id,
                generation_enabled=enabled,
                scene_space_ids=graph.scene_space_ids,
                shot_ids=graph.shot_ids,
                coverage_ids=graph.coverage_ids,
                constraint_ids=graph.constraint_ids,
                annotation_ids=graph.annotation_ids,
                provider_independent=True,
            )
        )
        self._audit(principal, acl_epoch, "director.generation", project_id, str(enabled))
        return stored

    def create_scene_space(
        self,
        *,
        project_id: str,
        scene_id: str,
        geometry_description: str,
        principal: Principal,
        acl_epoch: int,
        subject_positions: Sequence[SubjectPosition] = (),
        continuity_notes: str = "",
    ) -> SceneSpaceRecord:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        now = self.clock()
        space = SceneSpace(
            id=new_id("scene_space"),
            scene_id=scene_id,
            geometry_description=geometry_description,
            subject_positions=tuple(subject_positions),
        )
        record = SceneSpaceRecord(
            space=space,
            project_id=project_id,
            created_by_actor_id=principal.actor_id,
            created_at=now,
            continuity_notes=continuity_notes,
        )
        stored = self._put_space(record)
        stored = self._attach_config_node(stored, principal, acl_epoch)
        graph = self._graph(project_id)
        self._put_graph(
            DirectorVisionGraph(
                project_id=project_id,
                generation_enabled=graph.generation_enabled,
                scene_space_ids=(*graph.scene_space_ids, stored.space.id),
                shot_ids=graph.shot_ids,
                coverage_ids=graph.coverage_ids,
                constraint_ids=graph.constraint_ids,
                annotation_ids=graph.annotation_ids,
            )
        )
        self._audit(principal, acl_epoch, "director.create_space", stored.space.id, scene_id)
        return stored

    def get_scene_space(
        self,
        space_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> SceneSpaceRecord:
        record = self._load_space(space_id)
        self._require(principal, Action.READ, record.project_id, acl_epoch)
        return record

    def update_blocking(
        self,
        space_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        geometry_description: str | None = None,
        subject_positions: Sequence[SubjectPosition] | None = None,
        continuity_notes: str | None = None,
    ) -> SceneSpaceRecord:
        record = self._load_space(space_id)
        self._require(principal, Action.PROPOSE, record.project_id, acl_epoch)
        locked = set(record.space.locked_attributes)
        if geometry_description is not None and "geometry_description" in locked:
            if geometry_description != record.space.geometry_description:
                raise LockedGeometryError("geometry_description is locked")
        if subject_positions is not None and "subject_positions" in locked:
            if tuple(subject_positions) != record.space.subject_positions:
                raise LockedGeometryError("subject_positions is locked")
        space = SceneSpace(
            id=record.space.id,
            scene_id=record.space.scene_id,
            geometry_description=(
                record.space.geometry_description
                if geometry_description is None
                else geometry_description
            ),
            subject_positions=(
                record.space.subject_positions
                if subject_positions is None
                else tuple(subject_positions)
            ),
            locked_attributes=record.space.locked_attributes,
        )
        updated = SceneSpaceRecord(
            space=space,
            project_id=record.project_id,
            created_by_actor_id=record.created_by_actor_id,
            created_at=record.created_at,
            config_node_id=record.config_node_id,
            continuity_notes=(
                record.continuity_notes if continuity_notes is None else continuity_notes
            ),
        )
        stored = self._put_space(updated)
        self._invalidate_scene(stored, principal, acl_epoch)
        self._audit(principal, acl_epoch, "director.update_blocking", space_id, space.scene_id)
        return stored

    def lock_space_attribute(
        self,
        space_id: str,
        attribute: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> SceneSpaceRecord:
        record = self._load_space(space_id)
        self._require(principal, Action.MANAGE_PRODUCTION_LOCKS, record.project_id, acl_epoch)
        locked = record.space.locked_attributes
        if attribute not in locked:
            locked = (*locked, attribute)
        space = SceneSpace(
            id=record.space.id,
            scene_id=record.space.scene_id,
            geometry_description=record.space.geometry_description,
            subject_positions=record.space.subject_positions,
            locked_attributes=locked,
        )
        stored = self._put_space(
            SceneSpaceRecord(
                space=space,
                project_id=record.project_id,
                created_by_actor_id=record.created_by_actor_id,
                created_at=record.created_at,
                config_node_id=record.config_node_id,
                continuity_notes=record.continuity_notes,
            )
        )
        self._audit(principal, acl_epoch, "director.lock_space", space_id, attribute)
        return stored

    def add_coverage(
        self,
        *,
        project_id: str,
        scene_space_id: str,
        purpose: CoveragePurpose | str,
        principal: Principal,
        acl_epoch: int,
        shot_ids: Sequence[str] = (),
        notes: str = "",
    ) -> CoverageBeat:
        space = self._load_space(scene_space_id)
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        beat = CoverageBeat(
            id=f"cov_{new_ulid()}",
            project_id=project_id,
            scene_space_id=space.space.id,
            purpose=purpose if isinstance(purpose, CoveragePurpose) else CoveragePurpose(purpose),
            shot_ids=tuple(shot_ids),
            notes=notes,
        )
        stored = self._put_coverage(beat)
        graph = self._graph(project_id)
        self._put_graph(
            DirectorVisionGraph(
                project_id=project_id,
                generation_enabled=graph.generation_enabled,
                scene_space_ids=graph.scene_space_ids,
                shot_ids=graph.shot_ids,
                coverage_ids=(*graph.coverage_ids, stored.id),
                constraint_ids=graph.constraint_ids,
                annotation_ids=graph.annotation_ids,
            )
        )
        self._audit(principal, acl_epoch, "director.add_coverage", stored.id, scene_space_id)
        return stored

    def add_producer_constraint(
        self,
        *,
        project_id: str,
        target_kind: str,
        target_id: str,
        statement: str,
        principal: Principal,
        acl_epoch: int,
    ) -> ProducerConstraint:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        constraint = ProducerConstraint(
            id=f"pcn_{new_ulid()}",
            project_id=project_id,
            target_kind=target_kind,
            target_id=target_id,
            statement=statement,
            actor_id=principal.actor_id,
            created_at=self.clock(),
        )
        stored = self._put_constraint(constraint)
        graph = self._graph(project_id)
        self._put_graph(
            DirectorVisionGraph(
                project_id=project_id,
                generation_enabled=graph.generation_enabled,
                scene_space_ids=graph.scene_space_ids,
                shot_ids=graph.shot_ids,
                coverage_ids=graph.coverage_ids,
                constraint_ids=(*graph.constraint_ids, stored.id),
                annotation_ids=graph.annotation_ids,
            )
        )
        self._audit(principal, acl_epoch, "director.constraint", stored.id, target_id)
        return stored

    def annotate(
        self,
        *,
        project_id: str,
        target_kind: str,
        target_id: str,
        role: AnnotationRole | str,
        body: str,
        principal: Principal,
        acl_epoch: int,
        token: str | None = None,
        kind: str = "note",
        page_id: str = "",
    ) -> RoleAnnotation:
        parsed_role = role if isinstance(role, AnnotationRole) else AnnotationRole(str(role))
        action = Action.COMMENT if parsed_role is AnnotationRole.WRITER else Action.PROPOSE
        self._require(principal, action, project_id, acl_epoch)
        annotation = RoleAnnotation(
            id=f"ann_{new_ulid()}",
            project_id=project_id,
            role=parsed_role,
            target_kind=target_kind,
            target_id=target_id,
            body=body,
            actor_id=principal.actor_id,
            created_at=self.clock(),
            anchor=SemanticAnchor(
                id=f"anc_{new_ulid()}",
                token=token or f"sem_{new_ulid()}",
                kind=kind,
                page_id=page_id,
            ),
        )
        stored = self._put_annotation(annotation)
        graph = self._graph(project_id)
        self._put_graph(
            DirectorVisionGraph(
                project_id=project_id,
                generation_enabled=graph.generation_enabled,
                scene_space_ids=graph.scene_space_ids,
                shot_ids=graph.shot_ids,
                coverage_ids=graph.coverage_ids,
                constraint_ids=graph.constraint_ids,
                annotation_ids=(*graph.annotation_ids, stored.id),
            )
        )
        self._audit(principal, acl_epoch, "director.annotate", stored.id, parsed_role.value)
        return stored

    def transfer_annotation(
        self,
        annotation_id: str,
        *,
        page_id: str,
        principal: Principal,
        acl_epoch: int,
    ) -> RoleAnnotation:
        annotation = self._load_annotation(annotation_id)
        self._require(principal, Action.PROPOSE, annotation.project_id, acl_epoch)
        transferred = RoleAnnotation(
            id=annotation.id,
            project_id=annotation.project_id,
            role=annotation.role,
            target_kind=annotation.target_kind,
            target_id=annotation.target_id,
            body=annotation.body,
            actor_id=annotation.actor_id,
            created_at=annotation.created_at,
            anchor=SemanticAnchor(
                id=annotation.anchor.id,
                token=annotation.anchor.token,
                kind=annotation.anchor.kind,
                page_id=page_id,
            ),
        )
        stored = self._put_annotation(transferred)
        self._audit(principal, acl_epoch, "director.transfer_annotation", annotation_id, page_id)
        return stored

    def list_annotations(
        self,
        target_id: str,
        *,
        principal: Principal,
        project_id: str,
        acl_epoch: int,
        role: AnnotationRole | str | None = None,
    ) -> tuple[RoleAnnotation, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        parsed = None if role is None else (
            role if isinstance(role, AnnotationRole) else AnnotationRole(str(role))
        )
        found: list[RoleAnnotation] = []
        index = load_index(self.workspace)
        for annotation_id in index.get("annotation_ids", ()):
            digest = dict(index.get("annotation_digests", {})).get(str(annotation_id))
            if digest is None:
                continue
            item = RoleAnnotation.from_dict(load_payload(self.workspace, str(digest)))
            if item.project_id != project_id or item.target_id != target_id:
                continue
            if parsed is not None and item.role is not parsed:
                continue
            found.append(item)
        return tuple(found)

    def attach_shot(
        self,
        scene_space_id: str,
        shot_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> DirectorVisionGraph:
        space = self._load_space(scene_space_id)
        self._require(principal, Action.PROPOSE, space.project_id, acl_epoch)
        graph = self._graph(space.project_id)
        shot_ids = graph.shot_ids if shot_id in graph.shot_ids else (*graph.shot_ids, shot_id)
        stored = self._put_graph(
            DirectorVisionGraph(
                project_id=space.project_id,
                generation_enabled=graph.generation_enabled,
                scene_space_ids=graph.scene_space_ids,
                shot_ids=shot_ids,
                coverage_ids=graph.coverage_ids,
                constraint_ids=graph.constraint_ids,
                annotation_ids=graph.annotation_ids,
            )
        )
        return stored

    def notify_scene_changed(
        self,
        scene_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        project_id: str,
    ) -> tuple[str, ...]:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        return self._invalidate_scene_id(scene_id, principal, acl_epoch)

    def notify_intent_changed(
        self,
        scene_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        project_id: str,
    ) -> tuple[str, ...]:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        return self._invalidate_scene_id(scene_id, principal, acl_epoch)

    def config_node_id(self, scene_id: str) -> str | None:
        index = load_index(self.workspace)
        value = dict(index.get("scene_config_nodes", {})).get(scene_id)
        return str(value) if value else None

    def get_coverage(
        self,
        coverage_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> CoverageBeat:
        beat = self._load_coverage(coverage_id)
        self._require(principal, Action.READ, beat.project_id, acl_epoch)
        return beat

    def get_constraint(
        self,
        constraint_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> ProducerConstraint:
        constraint = self._load_constraint(constraint_id)
        self._require(principal, Action.READ, constraint.project_id, acl_epoch)
        return constraint

    def _graph(self, project_id: str) -> DirectorVisionGraph:
        index = load_index(self.workspace)
        digest = dict(index.get("graph_digests", {})).get(project_id)
        if digest is None:
            return DirectorVisionGraph(
                project_id=project_id,
                generation_enabled=False,
                scene_space_ids=(),
                shot_ids=(),
                coverage_ids=(),
                constraint_ids=(),
                annotation_ids=(),
            )
        return DirectorVisionGraph.from_dict(load_payload(self.workspace, str(digest)))

    def _attach_config_node(
        self,
        record: SceneSpaceRecord,
        principal: Principal,
        acl_epoch: int,
    ) -> SceneSpaceRecord:
        if self.dependencies is None:
            return record
        existing = self.config_node_id(record.space.scene_id)
        if existing:
            node_id = existing
        else:
            node = self.dependencies.add_node(
                project_id=record.project_id,
                kind=NodeKind.CONFIGURATION,
                principal=principal,
                acl_epoch=acl_epoch,
                subject_id=record.space.scene_id,
            )
            node_id = node.id

            def persist(index: dict[str, Any]) -> None:
                nodes = dict(index["scene_config_nodes"])
                nodes[record.space.scene_id] = node_id
                index["scene_config_nodes"] = nodes

            mutate_index(self.workspace, persist)
        updated = SceneSpaceRecord(
            space=record.space,
            project_id=record.project_id,
            created_by_actor_id=record.created_by_actor_id,
            created_at=record.created_at,
            config_node_id=node_id,
            continuity_notes=record.continuity_notes,
        )
        return self._put_space(updated)

    def _invalidate_scene(
        self,
        record: SceneSpaceRecord,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[str, ...]:
        return self._invalidate_scene_id(record.space.scene_id, principal, acl_epoch)

    def _invalidate_scene_id(
        self,
        scene_id: str,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[str, ...]:
        node_id = self.config_node_id(scene_id)
        if self.dependencies is None or not node_id:
            return ()
        result = self.dependencies.invalidate_inputs(
            [node_id],
            principal=principal,
            acl_epoch=acl_epoch,
        )
        return result.closure

    def _load_space(self, space_id: str) -> SceneSpaceRecord:
        index = load_index(self.workspace)
        digest = dict(index.get("space_digests", {})).get(space_id)
        if digest is None:
            raise SceneSpaceNotFoundError(f"scene space {space_id} is not in the graph")
        return SceneSpaceRecord.from_dict(load_payload(self.workspace, str(digest)))

    def _load_annotation(self, annotation_id: str) -> RoleAnnotation:
        index = load_index(self.workspace)
        digest = dict(index.get("annotation_digests", {})).get(annotation_id)
        if digest is None:
            raise AnnotationNotFoundError(f"annotation {annotation_id} is not in the graph")
        return RoleAnnotation.from_dict(load_payload(self.workspace, str(digest)))

    def _load_coverage(self, coverage_id: str) -> CoverageBeat:
        index = load_index(self.workspace)
        digest = dict(index.get("coverage_digests", {})).get(coverage_id)
        if digest is None:
            raise CoverageNotFoundError(f"coverage {coverage_id} is not in the graph")
        return CoverageBeat.from_dict(load_payload(self.workspace, str(digest)))

    def _load_constraint(self, constraint_id: str) -> ProducerConstraint:
        index = load_index(self.workspace)
        digest = dict(index.get("constraint_digests", {})).get(constraint_id)
        if digest is None:
            raise ConstraintNotFoundError(f"constraint {constraint_id} is not in the graph")
        return ProducerConstraint.from_dict(load_payload(self.workspace, str(digest)))

    def _put_graph(self, graph: DirectorVisionGraph) -> DirectorVisionGraph:
        def persist(index: dict[str, Any]) -> DirectorVisionGraph:
            _put_keyed(
                index,
                self.workspace,
                ids_key="graph_ids",
                digests_key="graph_digests",
                item_id=graph.project_id,
                payload=graph.to_dict(),
            )
            return graph

        return mutate_index(self.workspace, persist)

    def _put_space(self, record: SceneSpaceRecord) -> SceneSpaceRecord:
        def persist(index: dict[str, Any]) -> SceneSpaceRecord:
            _put_keyed(
                index,
                self.workspace,
                ids_key="space_ids",
                digests_key="space_digests",
                item_id=record.space.id,
                payload=record.to_dict(),
            )
            return record

        return mutate_index(self.workspace, persist)

    def _put_annotation(self, annotation: RoleAnnotation) -> RoleAnnotation:
        def persist(index: dict[str, Any]) -> RoleAnnotation:
            _put_keyed(
                index,
                self.workspace,
                ids_key="annotation_ids",
                digests_key="annotation_digests",
                item_id=annotation.id,
                payload=annotation.to_dict(),
            )
            return annotation

        return mutate_index(self.workspace, persist)

    def _put_coverage(self, beat: CoverageBeat) -> CoverageBeat:
        def persist(index: dict[str, Any]) -> CoverageBeat:
            _put_keyed(
                index,
                self.workspace,
                ids_key="coverage_ids",
                digests_key="coverage_digests",
                item_id=beat.id,
                payload=beat.to_dict(),
            )
            return beat

        return mutate_index(self.workspace, persist)

    def _put_constraint(self, constraint: ProducerConstraint) -> ProducerConstraint:
        def persist(index: dict[str, Any]) -> ProducerConstraint:
            _put_keyed(
                index,
                self.workspace,
                ids_key="constraint_ids",
                digests_key="constraint_digests",
                item_id=constraint.id,
                payload=constraint.to_dict(),
            )
            return constraint

        return mutate_index(self.workspace, persist)

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )

    def _audit(
        self,
        principal: Principal,
        acl_epoch: int,
        operation: str,
        object_id: str,
        reason: str,
    ) -> None:
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=operation,
            object_kind="director_vision",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
