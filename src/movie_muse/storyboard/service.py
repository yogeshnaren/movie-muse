"""ShotIR storyboards via ModelRouter and generic artifacts. Live image stays NOT_RUN."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from typing import Any

from movie_muse.artifacts.api import (
    ArtifactClassification,
    ArtifactComparison,
    ArtifactService,
    ArtifactType,
    RenderPurpose,
)
from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.director.api import AnnotationRole, DirectorVisionService
from movie_muse.identity.api import IdentityService, Principal, PrincipalKind
from movie_muse.model_router.api import ModelRequest, ModelRouter, RoleContract
from movie_muse.persistence.api import LocalWorkspace, digest_payload, utc_now
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import ArtifactStatus, new_ulid
from movie_muse.shot_ir.api import CAMERA_FIELDS, ShotIRService, StoredShot
from movie_muse.storyboard.errors import (
    AnnotationError,
    FrameNotFoundError,
    ImageProviderUnavailableError,
    LockedAttributeDriftError,
    StoryboardAcceptError,
)
from movie_muse.storyboard.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.storyboard.types import (
    DISCLAIMER,
    IMAGE_PROVIDER_ENV,
    RENDERER_VERSION,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    StoryboardAnnotation,
    StoryboardFrame,
    StoryboardMetrics,
)


def image_provider_base_url() -> str | None:
    value = os.environ.get(IMAGE_PROVIDER_ENV, "").strip()
    return value or None


def require_image_provider() -> str:
    base = image_provider_base_url()
    if not base:
        raise ImageProviderUnavailableError(
            f"{IMAGE_PROVIDER_ENV} is unset; EXT-IMAGE-PROVIDER stays NOT_RUN "
            "(fail-closed, not skipped; mocks do not satisfy the live gate)"
        )
    return base


class StoryboardService:
    """Diagrammatic ShotIR storyboards. Live image-provider smoke stays NOT_RUN."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        identity: IdentityService,
        audit: AuditLog,
        shots: ShotIRService,
        director: DirectorVisionService,
        artifacts: ArtifactService,
        router: ModelRouter,
        revisions: RevisionService,
        *,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.identity = identity
        self.audit = audit
        self.shots = shots
        self.director = director
        self.artifacts = artifacts
        self.router = router
        self.revisions = revisions
        self.clock = clock

    def render_frame(
        self,
        shot_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        style_key: str = "default-style",
        character_key: str | None = None,
        location_key: str | None = None,
        camera_overrides: Mapping[str, Any] | None = None,
    ) -> StoryboardFrame:
        shot = self.shots.get_shot(shot_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, shot.project_id, acl_epoch)
        self._assert_no_locked_drift(shot, camera_overrides)
        keys = self._continuity_keys(shot, style_key, character_key, location_key, principal, acl_epoch)
        prompt, fingerprint = self._prompt_and_fingerprint(shot, keys)
        reused = self._accepted_for_fingerprint(shot.project_id, fingerprint)
        if reused is not None:
            refreshed = self._with_freshness(reused, principal, acl_epoch)
            if refreshed.reused_accepted_asset:
                return refreshed
            marked = StoryboardFrame(
                id=refreshed.id,
                project_id=refreshed.project_id,
                shot_id=refreshed.shot_id,
                artifact_id=refreshed.artifact_id,
                artifact_version_id=refreshed.artifact_version_id,
                source_revision_id=refreshed.source_revision_id,
                prompt=refreshed.prompt,
                input_fingerprint=refreshed.input_fingerprint,
                style_key=refreshed.style_key,
                character_key=refreshed.character_key,
                location_key=refreshed.location_key,
                provenance=dict(refreshed.provenance),
                accepted=True,
                labeled_stale=refreshed.labeled_stale,
                image_provider_used=False,
                reused_accepted_asset=True,
                regeneration_count=refreshed.regeneration_count,
                accept_count=refreshed.accept_count,
                correction_count=refreshed.correction_count,
                parent_id=refreshed.parent_id,
            )
            written = self._put_frame(marked)
            self._audit(principal, acl_epoch, "storyboard.reuse", written.id, shot_id)
            return self._with_freshness(written, principal, acl_epoch)
        frame = self._materialize(
            shot,
            principal=principal,
            acl_epoch=acl_epoch,
            keys=keys,
            prompt=prompt,
            fingerprint=fingerprint,
            parent=None,
            regeneration_count=0,
            accept_count=0,
            correction_count=0,
        )
        self._audit(principal, acl_epoch, "storyboard.render", frame.id, shot_id)
        return self._with_freshness(frame, principal, acl_epoch)

    def regenerate(
        self, frame_id: str, *, principal: Principal, acl_epoch: int
    ) -> StoryboardFrame:
        prior = self.get_frame(frame_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, prior.project_id, acl_epoch)
        shot = self.shots.get_shot(prior.shot_id, principal=principal, acl_epoch=acl_epoch)
        keys = {
            "style_key": prior.style_key,
            "character_key": prior.character_key,
            "location_key": prior.location_key,
        }
        prompt, fingerprint = self._prompt_and_fingerprint(shot, keys)
        reused = self._accepted_for_fingerprint(shot.project_id, fingerprint)
        if reused is not None and reused.id != prior.id:
            self._audit(principal, acl_epoch, "storyboard.reuse", reused.id, prior.shot_id)
            return self._with_freshness(reused, principal, acl_epoch)
        frame = self._materialize(
            shot,
            principal=principal,
            acl_epoch=acl_epoch,
            keys=keys,
            prompt=prompt,
            fingerprint=fingerprint,
            parent=prior,
            regeneration_count=prior.regeneration_count + 1,
            accept_count=prior.accept_count,
            correction_count=prior.correction_count + (1 if prior.accepted else 0),
        )
        self._audit(principal, acl_epoch, "storyboard.regenerate", frame.id, prior.id)
        return self._with_freshness(frame, principal, acl_epoch)

    def accept_frame(
        self, frame_id: str, *, principal: Principal, acl_epoch: int
    ) -> StoryboardFrame:
        if principal.kind is not PrincipalKind.HUMAN:
            raise StoryboardAcceptError("only a human principal may accept a storyboard")
        stored = self.get_frame(frame_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.ACCEPT, stored.project_id, acl_epoch)
        if stored.accepted:
            return stored
        view = self.artifacts.get_version(
            stored.artifact_version_id, principal=principal, acl_epoch=acl_epoch
        )
        if view.status is ArtifactStatus.DRAFT:
            self.artifacts.transition_review(
                stored.artifact_version_id,
                ArtifactStatus.IN_REVIEW,
                principal=principal,
                acl_epoch=acl_epoch,
            )
        current = self.artifacts.get_version(
            stored.artifact_version_id, principal=principal, acl_epoch=acl_epoch
        )
        if current.status is ArtifactStatus.IN_REVIEW:
            self.artifacts.transition_review(
                stored.artifact_version_id,
                ArtifactStatus.APPROVED,
                principal=principal,
                acl_epoch=acl_epoch,
            )
        accepted = StoryboardFrame(
            id=stored.id,
            project_id=stored.project_id,
            shot_id=stored.shot_id,
            artifact_id=stored.artifact_id,
            artifact_version_id=stored.artifact_version_id,
            source_revision_id=stored.source_revision_id,
            prompt=stored.prompt,
            input_fingerprint=stored.input_fingerprint,
            style_key=stored.style_key,
            character_key=stored.character_key,
            location_key=stored.location_key,
            provenance=dict(stored.provenance),
            accepted=True,
            labeled_stale=stored.labeled_stale,
            image_provider_used=False,
            reused_accepted_asset=False,
            regeneration_count=stored.regeneration_count,
            accept_count=stored.accept_count + 1,
            correction_count=stored.correction_count,
            parent_id=stored.parent_id,
        )
        written = self._put_frame(accepted)
        self._audit(principal, acl_epoch, "storyboard.accept", written.id, stored.shot_id)
        return self._with_freshness(written, principal, acl_epoch)

    def compare_frames(
        self,
        left_id: str,
        right_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> ArtifactComparison:
        left = self.get_frame(left_id, principal=principal, acl_epoch=acl_epoch)
        right = self.get_frame(right_id, principal=principal, acl_epoch=acl_epoch)
        return self.artifacts.compare(
            left.artifact_version_id,
            right.artifact_version_id,
            principal=principal,
            acl_epoch=acl_epoch,
        )

    def annotate(
        self,
        frame_id: str,
        *,
        role: AnnotationRole | str,
        body: str,
        principal: Principal,
        acl_epoch: int,
    ) -> StoryboardAnnotation:
        stored = self.get_frame(frame_id, principal=principal, acl_epoch=acl_epoch)
        parsed = role if isinstance(role, AnnotationRole) else AnnotationRole(str(role))
        action = Action.COMMENT if parsed is AnnotationRole.WRITER else Action.PROPOSE
        self._require(principal, action, stored.project_id, acl_epoch)
        if not body.strip():
            raise AnnotationError("annotation body must not be empty")
        note = StoryboardAnnotation(
            id=f"sba_{new_ulid()}",
            frame_id=stored.id,
            role=parsed,
            body=body.strip(),
            actor_id=principal.actor_id,
            created_at=self.clock(),
        )
        written = self._put_annotation(note)
        self._audit(principal, acl_epoch, "storyboard.annotate", written.id, parsed.value)
        return written

    def list_annotations(
        self,
        frame_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        role: AnnotationRole | str | None = None,
    ) -> tuple[StoryboardAnnotation, ...]:
        stored = self.get_frame(frame_id, principal=principal, acl_epoch=acl_epoch)
        parsed: AnnotationRole | None = None
        if role is not None:
            parsed = role if isinstance(role, AnnotationRole) else AnnotationRole(str(role))
        index = load_index(self.workspace)
        found: list[StoryboardAnnotation] = []
        for annotation_id in index.get("annotation_ids", ()):
            digest = dict(index.get("annotation_digests", {})).get(str(annotation_id))
            if digest is None:
                continue
            item = StoryboardAnnotation.from_dict(load_payload(self.workspace, str(digest)))
            if item.frame_id != stored.id:
                continue
            if parsed is not None and item.role is not parsed:
                continue
            found.append(item)
        return tuple(found)

    def metrics(
        self, frame_id: str, *, principal: Principal, acl_epoch: int
    ) -> StoryboardMetrics:
        stored = self.get_frame(frame_id, principal=principal, acl_epoch=acl_epoch)
        return stored.metrics

    def live_render(
        self, frame_id: str, *, principal: Principal, acl_epoch: int
    ) -> StoryboardFrame:
        stored = self.get_frame(frame_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.RUN_PAID_PROVIDER, stored.project_id, acl_epoch)
        require_image_provider()
        raise ImageProviderUnavailableError(
            "configured image-provider smoke is not claimed as live evidence; "
            "EXT-IMAGE-PROVIDER stays NOT_RUN"
        )

    def get_frame(
        self, frame_id: str, *, principal: Principal, acl_epoch: int
    ) -> StoryboardFrame:
        stored = self._load_frame(frame_id)
        self._require(principal, Action.READ, stored.project_id, acl_epoch)
        return self._with_freshness(stored, principal, acl_epoch)

    def list_frames(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        shot_id: str | None = None,
    ) -> tuple[StoryboardFrame, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        index = load_index(self.workspace)
        ids = (
            list(dict(index.get("by_shot", {})).get(shot_id, []))
            if shot_id is not None
            else list(dict(index.get("by_project", {})).get(project_id, []))
        )
        found: list[StoryboardFrame] = []
        for frame_id in ids:
            digest = dict(index.get("frame_digests", {})).get(str(frame_id))
            if digest is None:
                continue
            item = StoryboardFrame.from_dict(load_payload(self.workspace, str(digest)))
            if item.project_id != project_id:
                continue
            found.append(self._with_freshness(item, principal, acl_epoch))
        return tuple(found)

    def _materialize(
        self,
        shot: StoredShot,
        *,
        principal: Principal,
        acl_epoch: int,
        keys: Mapping[str, str],
        prompt: str,
        fingerprint: str,
        parent: StoryboardFrame | None,
        regeneration_count: int,
        accept_count: int,
        correction_count: int,
    ) -> StoryboardFrame:
        self._ensure_template(shot.project_id, principal, acl_epoch)
        result = self._route_card(shot.project_id, principal, acl_epoch, prompt)
        artifact_id = parent.artifact_id if parent is not None else None
        if artifact_id is None:
            artifact = self.artifacts.create_artifact(
                project_id=shot.project_id,
                artifact_type=ArtifactType.MEDIA,
                title=f"Storyboard {shot.record.id}",
                principal=principal,
                acl_epoch=acl_epoch,
            )
            artifact_id = artifact.id
        source_revision_id = self.revisions.canon_head_id()
        version = self.artifacts.create_version(
            artifact_id,
            inputs={
                "disclaimer": DISCLAIMER,
                "prompt": prompt,
                "shot_id": shot.record.id,
                "style_key": keys["style_key"],
                "character_key": keys["character_key"],
                "location_key": keys["location_key"],
                "router_text": str(result.output.get("text", "")),
                "image_provider_used": False,
                "regeneration_count": regeneration_count,
            },
            source_revision_id=source_revision_id,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            renderer_version=RENDERER_VERSION,
            classification=ArtifactClassification.INTERNAL,
            principal=principal,
            acl_epoch=acl_epoch,
            purpose=RenderPurpose.REGENERATION if parent is not None else RenderPurpose.GENERATION,
        )
        frame = StoryboardFrame(
            id=f"stb_{new_ulid()}",
            project_id=shot.project_id,
            shot_id=shot.record.id,
            artifact_id=artifact_id,
            artifact_version_id=version.version.id,
            source_revision_id=source_revision_id,
            prompt=prompt,
            input_fingerprint=fingerprint,
            style_key=keys["style_key"],
            character_key=keys["character_key"],
            location_key=keys["location_key"],
            provenance=result.provenance.to_dict(),
            accepted=False,
            labeled_stale=shot.labeled_stale,
            image_provider_used=False,
            reused_accepted_asset=False,
            regeneration_count=regeneration_count,
            accept_count=accept_count,
            correction_count=correction_count,
            parent_id=parent.id if parent is not None else None,
        )
        return self._put_frame(frame)

    def _route_card(
        self, project_id: str, principal: Principal, acl_epoch: int, prompt: str
    ) -> Any:
        request = ModelRequest(
            capability="generate_text",
            data_classification="internal",
            latency_budget_ms=5000,
            cost_budget=5.0,
            offline_required=False,
            context_tokens=256,
            structured_output=True,
            quality_tier="fast",
            role_contract=RoleContract.EXECUTOR.value,
            project_id=project_id,
            actor_id=principal.actor_id,
            acl_epoch=acl_epoch,
            permission_snapshot_id=self.identity.permission_snapshot_id(),
            input={"text": prompt},
            consent_granted=True,
        )
        quote = self.router.quote(request)
        return self.router.execute(request, quote_id=quote.id)

    def _ensure_template(self, project_id: str, principal: Principal, acl_epoch: int) -> None:
        index = load_index(self.workspace)
        if index.get("template_ready"):
            return
        self.artifacts.register_template(
            project_id=project_id,
            template_id=TEMPLATE_ID,
            version=TEMPLATE_VERSION,
            renderer_version=RENDERER_VERSION,
            body="{{ disclaimer }}\n{{ prompt }}\n{{ router_text }}",
            principal=principal,
            acl_epoch=acl_epoch,
        )

        def mark(idx: dict[str, Any]) -> None:
            idx["template_ready"] = True

        mutate_index(self.workspace, mark)

    def _continuity_keys(
        self,
        shot: StoredShot,
        style_key: str,
        character_key: str | None,
        location_key: str | None,
        principal: Principal,
        acl_epoch: int,
    ) -> dict[str, str]:
        space = self.director.get_scene_space(
            shot.record.scene_space_id, principal=principal, acl_epoch=acl_epoch
        )
        subjects = ",".join(shot.record.eyeline_subject_ids) or "unspecified"
        return {
            "style_key": style_key,
            "character_key": character_key or subjects,
            "location_key": location_key or space.space.geometry_description,
        }

    def _prompt_and_fingerprint(
        self, shot: StoredShot, keys: Mapping[str, str]
    ) -> tuple[str, str]:
        camera = shot.record.camera
        locked = ",".join(shot.record.locked_attributes) or "none"
        prompt = "\n".join(
            [
                DISCLAIMER,
                f"SHOT {shot.record.id}",
                f"CAMERA lens_mm={camera.lens_mm} sensor={camera.sensor} "
                f"movement={camera.movement} height_m={camera.height_m}",
                f"LOCKED {locked}",
                f"STYLE {keys['style_key']}",
                f"CHARACTER {keys['character_key']}",
                f"LOCATION {keys['location_key']}",
                f"COMPOSITION {shot.record.composition_notes}",
                f"LIGHT {shot.record.light_direction}",
                f"COLOR {shot.color_intent}",
            ]
        )
        _, digest = digest_payload(
            {
                "shot_id": shot.record.id,
                "camera": camera.to_dict(),
                "locked": list(shot.record.locked_attributes),
                "keys": dict(keys),
                "composition": shot.record.composition_notes,
                "color_intent": shot.color_intent,
                "source_revision_id": self.revisions.canon_head_id(),
            }
        )
        return prompt, digest

    @staticmethod
    def _assert_no_locked_drift(
        shot: StoredShot, overrides: Mapping[str, Any] | None
    ) -> None:
        if not overrides:
            return
        locked = set(shot.record.locked_attributes)
        camera = shot.record.camera
        for name, incoming in overrides.items():
            if name not in locked:
                continue
            if name in CAMERA_FIELDS:
                current = getattr(camera, name)
            elif name == "color_intent":
                current = shot.color_intent
            elif name == "composition_notes":
                current = shot.record.composition_notes
            else:
                continue
            if incoming != current:
                raise LockedAttributeDriftError(
                    f"locked attribute {name} would drift from {current!r} to {incoming!r}"
                )

    def _accepted_for_fingerprint(
        self, project_id: str, fingerprint: str
    ) -> StoryboardFrame | None:
        index = load_index(self.workspace)
        frame_id = dict(index.get("by_fingerprint", {})).get(fingerprint)
        if frame_id is None:
            return None
        digest = dict(index.get("frame_digests", {})).get(str(frame_id))
        if digest is None:
            return None
        stored = StoryboardFrame.from_dict(load_payload(self.workspace, str(digest)))
        if stored.project_id != project_id or not stored.accepted:
            return None
        return stored

    def _with_freshness(
        self, stored: StoryboardFrame, principal: Principal, acl_epoch: int
    ) -> StoryboardFrame:
        shot = self.shots.get_shot(stored.shot_id, principal=principal, acl_epoch=acl_epoch)
        if shot.labeled_stale == stored.labeled_stale:
            return stored
        updated = StoryboardFrame(
            id=stored.id,
            project_id=stored.project_id,
            shot_id=stored.shot_id,
            artifact_id=stored.artifact_id,
            artifact_version_id=stored.artifact_version_id,
            source_revision_id=stored.source_revision_id,
            prompt=stored.prompt,
            input_fingerprint=stored.input_fingerprint,
            style_key=stored.style_key,
            character_key=stored.character_key,
            location_key=stored.location_key,
            provenance=dict(stored.provenance),
            accepted=stored.accepted,
            labeled_stale=shot.labeled_stale,
            image_provider_used=stored.image_provider_used,
            reused_accepted_asset=stored.reused_accepted_asset,
            regeneration_count=stored.regeneration_count,
            accept_count=stored.accept_count,
            correction_count=stored.correction_count,
            parent_id=stored.parent_id,
        )
        return self._put_frame(updated)

    def _load_frame(self, frame_id: str) -> StoryboardFrame:
        index = load_index(self.workspace)
        digest = dict(index.get("frame_digests", {})).get(frame_id)
        if digest is None:
            raise FrameNotFoundError(f"storyboard frame {frame_id} is not in the index")
        return StoryboardFrame.from_dict(load_payload(self.workspace, str(digest)))

    def _put_frame(self, stored: StoryboardFrame) -> StoryboardFrame:
        def persist(index: dict[str, Any]) -> StoryboardFrame:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("frame_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["frame_ids"] = ids
            digests = dict(index.get("frame_digests", {}))
            digests[stored.id] = digest
            index["frame_digests"] = digests
            by_project = dict(index.get("by_project", {}))
            project_ids = list(by_project.get(stored.project_id, []))
            if stored.id not in project_ids:
                project_ids.append(stored.id)
            by_project[stored.project_id] = project_ids
            index["by_project"] = by_project
            by_shot = dict(index.get("by_shot", {}))
            shot_ids = list(by_shot.get(stored.shot_id, []))
            if stored.id not in shot_ids:
                shot_ids.append(stored.id)
            by_shot[stored.shot_id] = shot_ids
            index["by_shot"] = by_shot
            fingerprints = dict(index.get("by_fingerprint", {}))
            if stored.accepted:
                fingerprints[stored.input_fingerprint] = stored.id
            index["by_fingerprint"] = fingerprints
            return stored

        return mutate_index(self.workspace, persist)

    def _put_annotation(self, stored: StoryboardAnnotation) -> StoryboardAnnotation:
        def persist(index: dict[str, Any]) -> StoryboardAnnotation:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("annotation_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["annotation_ids"] = ids
            digests = dict(index.get("annotation_digests", {}))
            digests[stored.id] = digest
            index["annotation_digests"] = digests
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
            object_kind="storyboard",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
