"""Provider-independent ShotIR with locked attributes and diagrammatic cards."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.dependencies.api import DependencyEngine, NodeKind, NodeState
from movie_muse.director.api import DirectorVisionService
from movie_muse.identity.api import Principal
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.schemas.api import CameraSpec, ShotIR, new_id
from movie_muse.shot_ir.errors import LockedAttributeError, ShotNotFoundError
from movie_muse.shot_ir.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.shot_ir.types import ShotCard, StoredShot

CAMERA_FIELDS = (
    "position_x",
    "position_y",
    "height_m",
    "orientation_degrees",
    "sensor",
    "lens_mm",
    "movement",
)


class ShotIRService:
    """Shot identity and camera definition. Models do not author ShotIR."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        director: DirectorVisionService,
        *,
        dependencies: DependencyEngine | None = None,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.director = director
        self.dependencies = dependencies
        self.clock = clock

    def create_shot(
        self,
        *,
        scene_space_id: str,
        camera: CameraSpec,
        composition_notes: str,
        light_direction: str,
        performance_intent: str,
        principal: Principal,
        acl_epoch: int,
        eyeline_subject_ids: Sequence[str] = (),
        color_intent: str = "unspecified",
        continuity_notes: str = "",
        coverage_purpose: str = "",
    ) -> StoredShot:
        space = self.director.get_scene_space(
            scene_space_id, principal=principal, acl_epoch=acl_epoch
        )
        self._require(principal, Action.PROPOSE, space.project_id, acl_epoch)
        record = ShotIR(
            id=new_id("shot"),
            scene_space_id=space.space.id,
            camera=camera,
            composition_notes=composition_notes,
            light_direction=light_direction,
            performance_intent=performance_intent,
            created_at=self.clock(),
            eyeline_subject_ids=tuple(eyeline_subject_ids),
        )
        stored = StoredShot(
            record=record,
            project_id=space.project_id,
            created_by_actor_id=principal.actor_id,
            color_intent=color_intent,
            continuity_notes=continuity_notes,
            coverage_purpose=coverage_purpose,
        )
        stored = self._put_shot(stored)
        stored = self._attach_analysis_node(stored, space.config_node_id, principal, acl_epoch)
        self.director.attach_shot(
            scene_space_id,
            stored.record.id,
            principal=principal,
            acl_epoch=acl_epoch,
        )
        self._audit(principal, acl_epoch, "shot_ir.create", stored.record.id, scene_space_id)
        return stored

    def get_shot(
        self,
        shot_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredShot:
        stored = self._load(shot_id)
        self._require(principal, Action.READ, stored.project_id, acl_epoch)
        return self._with_freshness(stored, principal, acl_epoch)

    def list_shots(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        scene_space_id: str | None = None,
    ) -> tuple[StoredShot, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        index = load_index(self.workspace)
        found: list[StoredShot] = []
        for shot_id in index.get("shot_ids", ()):
            digest = dict(index.get("shot_digests", {})).get(str(shot_id))
            if digest is None:
                continue
            item = StoredShot.from_dict(load_payload(self.workspace, str(digest)))
            if item.project_id != project_id:
                continue
            if scene_space_id is not None and item.record.scene_space_id != scene_space_id:
                continue
            found.append(self._with_freshness(item, principal, acl_epoch))
        return tuple(found)

    def update_camera(
        self,
        shot_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        camera: CameraSpec | None = None,
        composition_notes: str | None = None,
        light_direction: str | None = None,
        performance_intent: str | None = None,
        eyeline_subject_ids: Sequence[str] | None = None,
        color_intent: str | None = None,
        continuity_notes: str | None = None,
        coverage_purpose: str | None = None,
        annotations: Sequence[str] | None = None,
    ) -> StoredShot:
        stored = self._load(shot_id)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        locked = set(stored.record.locked_attributes)
        current = stored.record.camera
        next_camera = current if camera is None else camera
        for field in CAMERA_FIELDS:
            if field in locked and getattr(next_camera, field) != getattr(current, field):
                raise LockedAttributeError(f"camera.{field} is locked")
        for name, incoming, existing in (
            ("composition_notes", composition_notes, stored.record.composition_notes),
            ("light_direction", light_direction, stored.record.light_direction),
            ("performance_intent", performance_intent, stored.record.performance_intent),
            ("color_intent", color_intent, stored.color_intent),
        ):
            if incoming is not None and name in locked and incoming != existing:
                raise LockedAttributeError(f"{name} is locked")
        record = ShotIR(
            id=stored.record.id,
            scene_space_id=stored.record.scene_space_id,
            camera=next_camera,
            composition_notes=(
                stored.record.composition_notes
                if composition_notes is None
                else composition_notes
            ),
            light_direction=(
                stored.record.light_direction if light_direction is None else light_direction
            ),
            performance_intent=(
                stored.record.performance_intent
                if performance_intent is None
                else performance_intent
            ),
            created_at=stored.record.created_at,
            eyeline_subject_ids=(
                stored.record.eyeline_subject_ids
                if eyeline_subject_ids is None
                else tuple(eyeline_subject_ids)
            ),
            locked_attributes=stored.record.locked_attributes,
            annotations=(
                stored.record.annotations if annotations is None else tuple(annotations)
            ),
        )
        updated = StoredShot(
            record=record,
            project_id=stored.project_id,
            created_by_actor_id=stored.created_by_actor_id,
            color_intent=stored.color_intent if color_intent is None else color_intent,
            continuity_notes=(
                stored.continuity_notes if continuity_notes is None else continuity_notes
            ),
            coverage_purpose=(
                stored.coverage_purpose if coverage_purpose is None else coverage_purpose
            ),
            analysis_node_id=stored.analysis_node_id,
            labeled_stale=stored.labeled_stale,
        )
        written = self._put_shot(updated)
        self._audit(principal, acl_epoch, "shot_ir.update", shot_id, "camera")
        return written

    def lock_attribute(
        self,
        shot_id: str,
        attribute: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredShot:
        stored = self._load(shot_id)
        self._require(principal, Action.MANAGE_PRODUCTION_LOCKS, stored.project_id, acl_epoch)
        locked = stored.record.locked_attributes
        if attribute not in locked:
            locked = (*locked, attribute)
        record = ShotIR(
            id=stored.record.id,
            scene_space_id=stored.record.scene_space_id,
            camera=stored.record.camera,
            composition_notes=stored.record.composition_notes,
            light_direction=stored.record.light_direction,
            performance_intent=stored.record.performance_intent,
            created_at=stored.record.created_at,
            eyeline_subject_ids=stored.record.eyeline_subject_ids,
            locked_attributes=locked,
            annotations=stored.record.annotations,
        )
        written = self._put_shot(
            StoredShot(
                record=record,
                project_id=stored.project_id,
                created_by_actor_id=stored.created_by_actor_id,
                color_intent=stored.color_intent,
                continuity_notes=stored.continuity_notes,
                coverage_purpose=stored.coverage_purpose,
                analysis_node_id=stored.analysis_node_id,
                labeled_stale=stored.labeled_stale,
            )
        )
        self._audit(principal, acl_epoch, "shot_ir.lock", shot_id, attribute)
        return written

    def unlock_attribute(
        self,
        shot_id: str,
        attribute: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredShot:
        stored = self._load(shot_id)
        self._require(principal, Action.MANAGE_PRODUCTION_LOCKS, stored.project_id, acl_epoch)
        locked = tuple(item for item in stored.record.locked_attributes if item != attribute)
        record = ShotIR(
            id=stored.record.id,
            scene_space_id=stored.record.scene_space_id,
            camera=stored.record.camera,
            composition_notes=stored.record.composition_notes,
            light_direction=stored.record.light_direction,
            performance_intent=stored.record.performance_intent,
            created_at=stored.record.created_at,
            eyeline_subject_ids=stored.record.eyeline_subject_ids,
            locked_attributes=locked,
            annotations=stored.record.annotations,
        )
        written = self._put_shot(
            StoredShot(
                record=record,
                project_id=stored.project_id,
                created_by_actor_id=stored.created_by_actor_id,
                color_intent=stored.color_intent,
                continuity_notes=stored.continuity_notes,
                coverage_purpose=stored.coverage_purpose,
                analysis_node_id=stored.analysis_node_id,
                labeled_stale=stored.labeled_stale,
            )
        )
        self._audit(principal, acl_epoch, "shot_ir.unlock", shot_id, attribute)
        return written

    def attach_annotation(
        self,
        shot_id: str,
        annotation_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredShot:
        stored = self._load(shot_id)
        self._require(principal, Action.COMMENT, stored.project_id, acl_epoch)
        annotations = stored.record.annotations
        if annotation_id not in annotations:
            annotations = (*annotations, annotation_id)
        return self.update_camera(
            shot_id,
            principal=principal,
            acl_epoch=acl_epoch,
            annotations=annotations,
        )

    def shot_card(
        self,
        shot_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> ShotCard:
        stored = self.get_shot(shot_id, principal=principal, acl_epoch=acl_epoch)
        space = self.director.get_scene_space(
            stored.record.scene_space_id, principal=principal, acl_epoch=acl_epoch
        )
        graph = self.director.graph(stored.project_id, principal=principal, acl_epoch=acl_epoch)
        camera = stored.record.camera
        camera_summary = (
            f"pos=({camera.position_x:.2f},{camera.position_y:.2f}) "
            f"h={camera.height_m:.2f}m lens={camera.lens_mm:.1f}mm "
            f"sensor={camera.sensor} movement={camera.movement} "
            f"orientation={camera.orientation_degrees:.1f}"
        )
        blocking = "; ".join(
            f"{item.subject_id}@({item.x:.2f},{item.y:.2f})"
            for item in space.space.subject_positions
        ) or "empty"
        diagram = "\n".join(
            (
                f"SHOT {stored.record.id}",
                f"SPACE {space.space.id} scene={space.space.scene_id}",
                f"GEO {space.space.geometry_description}",
                f"BLOCK {blocking}",
                f"CAM {camera_summary}",
                f"EYE {','.join(stored.record.eyeline_subject_ids) or 'none'}",
                f"LIGHT {stored.record.light_direction}",
                f"PERF {stored.record.performance_intent}",
                f"COLOR {stored.color_intent}",
                "RENDER diagrammatic; generation_used=false",
            )
        )
        return ShotCard(
            shot_id=stored.record.id,
            scene_space_id=space.space.id,
            diagram=diagram,
            camera_summary=camera_summary,
            blocking_summary=blocking,
            generation_used=False,
            mode="diagrammatic",
            generation_enabled=graph.generation_enabled,
        )

    def _attach_analysis_node(
        self,
        stored: StoredShot,
        config_node_id: str | None,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredShot:
        if self.dependencies is None or not config_node_id:
            return stored
        node = self.dependencies.add_node(
            project_id=stored.project_id,
            kind=NodeKind.DERIVED_PROJECTION,
            principal=principal,
            acl_epoch=acl_epoch,
            input_ids=(config_node_id,),
            subject_id=stored.record.id,
        )
        updated = StoredShot(
            record=stored.record,
            project_id=stored.project_id,
            created_by_actor_id=stored.created_by_actor_id,
            color_intent=stored.color_intent,
            continuity_notes=stored.continuity_notes,
            coverage_purpose=stored.coverage_purpose,
            analysis_node_id=node.id,
            labeled_stale=False,
        )
        return self._put_shot(updated)

    def _with_freshness(
        self, stored: StoredShot, principal: Principal, acl_epoch: int
    ) -> StoredShot:
        if self.dependencies is None or not stored.analysis_node_id:
            return stored
        view = self.dependencies.view_node(
            stored.analysis_node_id, principal=principal, acl_epoch=acl_epoch
        )
        labeled = view.state is NodeState.STALE
        if labeled == stored.labeled_stale:
            return stored
        return StoredShot(
            record=stored.record,
            project_id=stored.project_id,
            created_by_actor_id=stored.created_by_actor_id,
            color_intent=stored.color_intent,
            continuity_notes=stored.continuity_notes,
            coverage_purpose=stored.coverage_purpose,
            analysis_node_id=stored.analysis_node_id,
            labeled_stale=labeled,
        )

    def _load(self, shot_id: str) -> StoredShot:
        index = load_index(self.workspace)
        digest = dict(index.get("shot_digests", {})).get(shot_id)
        if digest is None:
            raise ShotNotFoundError(f"shot {shot_id} is not in the index")
        return StoredShot.from_dict(load_payload(self.workspace, str(digest)))

    def _put_shot(self, stored: StoredShot) -> StoredShot:
        def persist(index: dict[str, Any]) -> StoredShot:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index["shot_ids"])
            if stored.record.id not in ids:
                ids.append(stored.record.id)
            index["shot_ids"] = ids
            digests = dict(index["shot_digests"])
            digests[stored.record.id] = digest
            index["shot_digests"] = digests
            return stored

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
            object_kind="shot_ir",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
