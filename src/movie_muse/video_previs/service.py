"""Queued Veo/replaceable video previs. Live video stays NOT_RUN. Never canon."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
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
from movie_muse.identity.api import IdentityService, Principal, PrincipalKind
from movie_muse.jobs.api import Job, JobService, JobStatus
from movie_muse.model_router.api import ModelRequest, ModelRouter, RoleContract
from movie_muse.persistence.api import LocalWorkspace, digest_payload, utc_now
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import ArtifactStatus, new_ulid
from movie_muse.shot_ir.api import ShotIRService, StoredShot
from movie_muse.storyboard.api import StoryboardService
from movie_muse.video_previs.errors import (
    CanonPromotionError,
    ClipNotFoundError,
    ConsentRequiredError,
    QueueError,
    TimelineNotFoundError,
    VideoPrevisAcceptError,
    VideoProviderUnavailableError,
)
from movie_muse.video_previs.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.video_previs.types import (
    CONTINUITY_LIMITATIONS,
    DISCLAIMER,
    JOB_TYPE,
    RENDERER_VERSION,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    VIDEO_PROVIDER_ENV,
    WORKER_ID,
    ConsentRecord,
    ConsentState,
    CostRange,
    IntendedEffectReview,
    PrevisTimeline,
    TimelineKind,
    VideoClip,
)


def video_provider_base_url() -> str | None:
    value = os.environ.get(VIDEO_PROVIDER_ENV, "").strip()
    return value or None


def require_video_provider() -> str:
    base = video_provider_base_url()
    if not base:
        raise VideoProviderUnavailableError(
            f"{VIDEO_PROVIDER_ENV} is unset; EXT-VIDEO-PROVIDER stays NOT_RUN "
            "(fail-closed, not skipped; mocks do not satisfy the live gate)"
        )
    return base


class VideoPrevisService:
    """Durable video previs queue. Live video-provider smoke stays NOT_RUN."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        identity: IdentityService,
        audit: AuditLog,
        shots: ShotIRService,
        storyboard: StoryboardService,
        artifacts: ArtifactService,
        router: ModelRouter,
        revisions: RevisionService,
        jobs: JobService,
        *,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.identity = identity
        self.audit = audit
        self.shots = shots
        self.storyboard = storyboard
        self.artifacts = artifacts
        self.router = router
        self.revisions = revisions
        self.jobs = jobs
        self.clock = clock

    def consent_view(self, project_id: str) -> ConsentRecord:
        index = load_index(self.workspace)
        raw = dict(index.get("consent", {})).get(project_id)
        if not isinstance(raw, dict):
            return ConsentRecord(project_id=project_id, state=ConsentState.PENDING)
        return ConsentRecord.from_dict({"project_id": project_id, **raw})

    def grant_consent(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> ConsentRecord:
        if principal.kind is not PrincipalKind.HUMAN:
            raise ConsentRequiredError("only a human principal may grant video-previs consent")
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        record = ConsentRecord(
            project_id=project_id,
            state=ConsentState.GRANTED,
            actor_id=principal.actor_id,
            decided_at=self.clock(),
        )
        self._put_consent(record)
        self._audit(principal, acl_epoch, "video_previs.consent_grant", project_id, "granted")
        return record

    def deny_consent(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> ConsentRecord:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        record = ConsentRecord(
            project_id=project_id,
            state=ConsentState.DENIED,
            actor_id=principal.actor_id,
            decided_at=self.clock(),
        )
        self._put_consent(record)
        self._audit(principal, acl_epoch, "video_previs.consent_deny", project_id, "denied")
        return record

    def withdraw_consent(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> ConsentRecord:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        record = ConsentRecord(
            project_id=project_id,
            state=ConsentState.WITHDRAWN,
            actor_id=principal.actor_id,
            decided_at=self.clock(),
        )
        self._put_consent(record)
        self._audit(principal, acl_epoch, "video_previs.consent_withdraw", project_id, "withdrawn")
        return record

    def preflight(
        self,
        shot_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        storyboard_frame_id: str | None = None,
    ) -> CostRange:
        shot = self.shots.get_shot(shot_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, shot.project_id, acl_epoch)
        prompt, _fingerprint = self._prompt_and_fingerprint(shot, storyboard_frame_id, 0)
        quote = self.router.quote(self._model_request(shot.project_id, principal, acl_epoch, prompt))
        low = round(quote.estimated_cost * 0.5, 6)
        high = round(max(quote.estimated_cost * 2.0, quote.estimated_cost), 6)
        return CostRange(
            estimated_cost=quote.estimated_cost,
            low=low,
            high=high,
            currency=quote.currency,
            quote_id=quote.id,
            paid=quote.paid,
        )

    def enqueue_clip(
        self,
        shot_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        storyboard_frame_id: str | None = None,
        parent: VideoClip | None = None,
    ) -> VideoClip:
        shot = self.shots.get_shot(shot_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, shot.project_id, acl_epoch)
        self._require_consent(shot.project_id)
        if storyboard_frame_id is not None:
            frame = self.storyboard.get_frame(
                storyboard_frame_id, principal=principal, acl_epoch=acl_epoch
            )
            if frame.shot_id != shot.record.id:
                raise QueueError("storyboard frame does not belong to the requested shot")
        regeneration_count = 0 if parent is None else parent.regeneration_count + 1
        prompt, fingerprint = self._prompt_and_fingerprint(
            shot, storyboard_frame_id, regeneration_count
        )
        reused = self._clip_for_fingerprint(shot.project_id, fingerprint)
        if reused is not None:
            refreshed = self._with_freshness(reused, principal, acl_epoch)
            if refreshed.accepted:
                marked = VideoClip(
                    id=refreshed.id,
                    project_id=refreshed.project_id,
                    shot_id=refreshed.shot_id,
                    job_id=refreshed.job_id,
                    source_revision_id=refreshed.source_revision_id,
                    prompt=refreshed.prompt,
                    input_fingerprint=refreshed.input_fingerprint,
                    estimated_cost_low=refreshed.estimated_cost_low,
                    estimated_cost_high=refreshed.estimated_cost_high,
                    storyboard_frame_id=refreshed.storyboard_frame_id,
                    artifact_id=refreshed.artifact_id,
                    artifact_version_id=refreshed.artifact_version_id,
                    provenance=dict(refreshed.provenance or {}),
                    actual_cost=refreshed.actual_cost,
                    accepted=True,
                    labeled_stale=refreshed.labeled_stale,
                    video_provider_used=False,
                    reused_accepted_asset=True,
                    labeled_previs=True,
                    canon=False,
                    regeneration_count=refreshed.regeneration_count,
                    parent_id=refreshed.parent_id,
                )
                written = self._put_clip(marked)
                self._audit(principal, acl_epoch, "video_previs.reuse", written.id, shot_id)
                return self._with_freshness(written, principal, acl_epoch)
            return refreshed
        costs = self.preflight(
            shot_id,
            principal=principal,
            acl_epoch=acl_epoch,
            storyboard_frame_id=storyboard_frame_id,
        )
        clip_id = f"vpv_{new_ulid()}"
        job = self.jobs.enqueue(
            JOB_TYPE,
            {
                "authorization": {"action": "propose"},
                "estimated_cost": costs.estimated_cost,
                "clip_id": clip_id,
                "shot_id": shot.record.id,
                "disclaimer": DISCLAIMER,
            },
            actor_id=principal.actor_id,
            project_id=shot.project_id,
            idempotency_key=f"video-previs:{fingerprint}",
            priority=10,
            cost_budget=max(5.0, costs.high * 2.0, costs.estimated_cost + 1.0),
            timeout_seconds=120,
            max_attempts=3,
            input_fingerprint=fingerprint,
            acl_epoch=acl_epoch,
            permission_snapshot_id=self.identity.permission_snapshot_id(),
            trace_id=f"trc_{new_ulid()}",
        )
        clip = VideoClip(
            id=clip_id,
            project_id=shot.project_id,
            shot_id=shot.record.id,
            job_id=job.id,
            source_revision_id=self.revisions.canon_head_id(),
            prompt=prompt,
            input_fingerprint=fingerprint,
            estimated_cost_low=costs.low,
            estimated_cost_high=costs.high,
            storyboard_frame_id=storyboard_frame_id,
            labeled_stale=shot.labeled_stale,
            labeled_previs=True,
            canon=False,
            regeneration_count=regeneration_count,
            parent_id=parent.id if parent is not None else None,
        )
        written = self._put_clip(clip)
        self._audit(principal, acl_epoch, "video_previs.enqueue", written.id, job.id)
        return self._with_freshness(written, principal, acl_epoch)

    def complete_local(
        self, clip_id: str, *, principal: Principal, acl_epoch: int
    ) -> VideoClip:
        stored = self.get_clip(clip_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        self._require_consent(stored.project_id)
        if stored.artifact_id:
            return stored
        job = self._lease_job(stored.job_id)
        self.jobs.heartbeat(job.id, WORKER_ID, progress=0.5)
        shot = self.shots.get_shot(stored.shot_id, principal=principal, acl_epoch=acl_epoch)
        result = self._route_card(shot.project_id, principal, acl_epoch, stored.prompt)
        self._ensure_template(shot.project_id, principal, acl_epoch)
        artifact = self.artifacts.create_artifact(
            project_id=shot.project_id,
            artifact_type=ArtifactType.MEDIA,
            title=f"Previs {stored.id}",
            principal=principal,
            acl_epoch=acl_epoch,
        )
        source_revision_id = self.revisions.canon_head_id()
        version = self.artifacts.create_version(
            artifact.id,
            inputs={
                "disclaimer": DISCLAIMER,
                "continuity_limitations": CONTINUITY_LIMITATIONS,
                "prompt": stored.prompt,
                "shot_id": stored.shot_id,
                "clip_id": stored.id,
                "router_text": str(result.output.get("text", "")),
                "video_provider_used": False,
                "labeled_previs": True,
                "canon": False,
                "regeneration_count": stored.regeneration_count,
            },
            source_revision_id=source_revision_id,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            renderer_version=RENDERER_VERSION,
            classification=ArtifactClassification.INTERNAL,
            principal=principal,
            acl_epoch=acl_epoch,
            purpose=(
                RenderPurpose.REGENERATION
                if stored.parent_id is not None
                else RenderPurpose.GENERATION
            ),
        )
        actual_cost = float(result.usage.actual_cost)
        completed = self.jobs.complete(
            job.id,
            WORKER_ID,
            {
                "clip_id": stored.id,
                "artifact_id": artifact.id,
                "artifact_version_id": version.version.id,
                "actual_cost": actual_cost,
                "labeled_previs": True,
                "canon": False,
            },
        )
        clip = VideoClip(
            id=stored.id,
            project_id=stored.project_id,
            shot_id=stored.shot_id,
            job_id=completed.id,
            source_revision_id=source_revision_id,
            prompt=stored.prompt,
            input_fingerprint=stored.input_fingerprint,
            estimated_cost_low=stored.estimated_cost_low,
            estimated_cost_high=stored.estimated_cost_high,
            storyboard_frame_id=stored.storyboard_frame_id,
            artifact_id=artifact.id,
            artifact_version_id=version.version.id,
            provenance=result.provenance.to_dict(),
            actual_cost=actual_cost,
            accepted=False,
            labeled_stale=shot.labeled_stale,
            video_provider_used=False,
            reused_accepted_asset=False,
            labeled_previs=True,
            canon=False,
            regeneration_count=stored.regeneration_count,
            parent_id=stored.parent_id,
        )
        written = self._put_clip(clip)
        self._audit(principal, acl_epoch, "video_previs.complete_local", written.id, completed.id)
        return self._with_freshness(written, principal, acl_epoch)

    def record_provider_failure(
        self,
        clip_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        error: str,
        retryable: bool,
    ) -> Job:
        stored = self.get_clip(clip_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        job = self.jobs.get(stored.job_id)
        if job.status is not JobStatus.LEASED:
            job = self._lease_job(stored.job_id)
        failed = self.jobs.fail(job.id, WORKER_ID, error, retryable)
        self._audit(principal, acl_epoch, "video_previs.fail", stored.id, failed.status.value)
        return failed

    def cancel_clip(
        self, clip_id: str, *, principal: Principal, acl_epoch: int
    ) -> Job:
        stored = self.get_clip(clip_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        canceled = self.jobs.cancel(stored.job_id, principal.actor_id)
        self._audit(principal, acl_epoch, "video_previs.cancel", stored.id, canceled.id)
        return canceled

    def progress(self, clip_id: str, *, principal: Principal, acl_epoch: int) -> float:
        stored = self.get_clip(clip_id, principal=principal, acl_epoch=acl_epoch)
        return self.jobs.get(stored.job_id).progress

    def job_for(self, clip_id: str, *, principal: Principal, acl_epoch: int) -> Job:
        stored = self.get_clip(clip_id, principal=principal, acl_epoch=acl_epoch)
        return self.jobs.get(stored.job_id)

    def regenerate(
        self, clip_id: str, *, principal: Principal, acl_epoch: int
    ) -> VideoClip:
        prior = self.get_clip(clip_id, principal=principal, acl_epoch=acl_epoch)
        return self.enqueue_clip(
            prior.shot_id,
            principal=principal,
            acl_epoch=acl_epoch,
            storyboard_frame_id=prior.storyboard_frame_id,
            parent=prior,
        )

    def accept_clip(
        self, clip_id: str, *, principal: Principal, acl_epoch: int
    ) -> VideoClip:
        if principal.kind is not PrincipalKind.HUMAN:
            raise VideoPrevisAcceptError("only a human principal may accept video previs")
        stored = self.get_clip(clip_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.ACCEPT, stored.project_id, acl_epoch)
        if stored.accepted:
            return stored
        if not stored.artifact_version_id:
            raise QueueError("cannot accept a previs clip before local complete")
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
        accepted = VideoClip(
            id=stored.id,
            project_id=stored.project_id,
            shot_id=stored.shot_id,
            job_id=stored.job_id,
            source_revision_id=stored.source_revision_id,
            prompt=stored.prompt,
            input_fingerprint=stored.input_fingerprint,
            estimated_cost_low=stored.estimated_cost_low,
            estimated_cost_high=stored.estimated_cost_high,
            storyboard_frame_id=stored.storyboard_frame_id,
            artifact_id=stored.artifact_id,
            artifact_version_id=stored.artifact_version_id,
            provenance=dict(stored.provenance or {}),
            actual_cost=stored.actual_cost,
            accepted=True,
            labeled_stale=stored.labeled_stale,
            video_provider_used=False,
            reused_accepted_asset=False,
            labeled_previs=True,
            canon=False,
            regeneration_count=stored.regeneration_count,
            parent_id=stored.parent_id,
        )
        written = self._put_clip(accepted)
        self._audit(principal, acl_epoch, "video_previs.accept", written.id, stored.shot_id)
        return self._with_freshness(written, principal, acl_epoch)

    def compare_clips(
        self,
        left_id: str,
        right_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> ArtifactComparison:
        left = self.get_clip(left_id, principal=principal, acl_epoch=acl_epoch)
        right = self.get_clip(right_id, principal=principal, acl_epoch=acl_epoch)
        if not left.artifact_version_id or not right.artifact_version_id:
            raise QueueError("compare requires completed previs clips")
        return self.artifacts.compare(
            left.artifact_version_id,
            right.artifact_version_id,
            principal=principal,
            acl_epoch=acl_epoch,
        )

    def assemble_timeline(
        self,
        clip_ids: Sequence[str],
        *,
        principal: Principal,
        acl_epoch: int,
        kind: TimelineKind | str = TimelineKind.TIMELINE,
    ) -> PrevisTimeline:
        if not clip_ids:
            raise QueueError("timeline assembly requires at least one clip")
        parsed = kind if isinstance(kind, TimelineKind) else TimelineKind(str(kind))
        clips = [
            self.get_clip(clip_id, principal=principal, acl_epoch=acl_epoch) for clip_id in clip_ids
        ]
        project_id = clips[0].project_id
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        self._require_consent(project_id)
        for clip in clips:
            if clip.project_id != project_id:
                raise QueueError("timeline clips must belong to one project")
            if not clip.artifact_id:
                raise QueueError("timeline assembly requires completed previs clips")
            if clip.canon:
                raise CanonPromotionError("generated video is never canon by itself")
        self._ensure_template(project_id, principal, acl_epoch)
        artifact = self.artifacts.create_artifact(
            project_id=project_id,
            artifact_type=ArtifactType.PACKAGE,
            title=f"Previs {parsed.value}",
            principal=principal,
            acl_epoch=acl_epoch,
        )
        version = self.artifacts.create_version(
            artifact.id,
            inputs={
                "disclaimer": DISCLAIMER,
                "continuity_limitations": CONTINUITY_LIMITATIONS,
                "kind": parsed.value,
                "clip_ids": list(clip_ids),
                "labeled_previs": True,
                "canon": False,
            },
            source_revision_id=self.revisions.canon_head_id(),
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            renderer_version=RENDERER_VERSION,
            classification=ArtifactClassification.INTERNAL,
            principal=principal,
            acl_epoch=acl_epoch,
            purpose=RenderPurpose.GENERATION,
        )
        timeline = PrevisTimeline(
            id=f"vtl_{new_ulid()}",
            project_id=project_id,
            clip_ids=tuple(clip_ids),
            artifact_id=artifact.id,
            artifact_version_id=version.version.id,
            kind=parsed,
            labeled_previs=True,
            canon=False,
        )
        written = self._put_timeline(timeline)
        self._audit(principal, acl_epoch, "video_previs.assemble", written.id, parsed.value)
        return written

    def review_intended_effect(
        self,
        subject_id: str,
        *,
        notes: str,
        principal: Principal,
        acl_epoch: int,
        promote_to_canon: bool = False,
    ) -> IntendedEffectReview:
        if promote_to_canon:
            raise CanonPromotionError("generated video is never canon by itself")
        if principal.kind is not PrincipalKind.HUMAN:
            raise VideoPrevisAcceptError("only a human principal may review intended effect")
        if not notes.strip():
            raise QueueError("intended-effect review notes must not be empty")
        project_id = self._subject_project(subject_id, principal, acl_epoch)
        self._require(principal, Action.ACCEPT, project_id, acl_epoch)
        review = IntendedEffectReview(
            id=f"vie_{new_ulid()}",
            project_id=project_id,
            subject_id=subject_id,
            notes=notes.strip(),
            actor_id=principal.actor_id,
            created_at=self.clock(),
            promotes_to_canon=False,
        )
        written = self._put_review(review)
        self._audit(principal, acl_epoch, "video_previs.review", written.id, subject_id)
        return written

    def live_render(
        self, clip_id: str, *, principal: Principal, acl_epoch: int
    ) -> VideoClip:
        stored = self.get_clip(clip_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.RUN_PAID_PROVIDER, stored.project_id, acl_epoch)
        self._require_consent(stored.project_id)
        require_video_provider()
        raise VideoProviderUnavailableError(
            "configured video-provider smoke is not claimed as live evidence; "
            "EXT-VIDEO-PROVIDER stays NOT_RUN"
        )

    def get_clip(
        self, clip_id: str, *, principal: Principal, acl_epoch: int
    ) -> VideoClip:
        stored = self._load_clip(clip_id)
        self._require(principal, Action.READ, stored.project_id, acl_epoch)
        return self._with_freshness(stored, principal, acl_epoch)

    def list_clips(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        shot_id: str | None = None,
    ) -> tuple[VideoClip, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        index = load_index(self.workspace)
        ids = (
            list(dict(index.get("by_shot", {})).get(shot_id, []))
            if shot_id is not None
            else list(dict(index.get("by_project", {})).get(project_id, []))
        )
        found: list[VideoClip] = []
        for clip_id in ids:
            digest = dict(index.get("clip_digests", {})).get(str(clip_id))
            if digest is None:
                continue
            item = VideoClip.from_dict(load_payload(self.workspace, str(digest)))
            if item.project_id != project_id:
                continue
            found.append(self._with_freshness(item, principal, acl_epoch))
        return tuple(found)

    def get_timeline(
        self, timeline_id: str, *, principal: Principal, acl_epoch: int
    ) -> PrevisTimeline:
        stored = self._load_timeline(timeline_id)
        self._require(principal, Action.READ, stored.project_id, acl_epoch)
        return stored

    def _subject_project(
        self, subject_id: str, principal: Principal, acl_epoch: int
    ) -> str:
        index = load_index(self.workspace)
        if subject_id in dict(index.get("clip_digests", {})):
            return self.get_clip(subject_id, principal=principal, acl_epoch=acl_epoch).project_id
        if subject_id in dict(index.get("timeline_digests", {})):
            return self.get_timeline(
                subject_id, principal=principal, acl_epoch=acl_epoch
            ).project_id
        raise ClipNotFoundError(f"previs subject {subject_id} is not in the index")

    def _lease_job(self, job_id: str) -> Job:
        current = self.jobs.get(job_id)
        if current.status is JobStatus.LEASED:
            if current.worker_id != WORKER_ID:
                raise QueueError(f"job {job_id} is leased by another worker")
            return current
        if current.status not in {JobStatus.QUEUED, JobStatus.RETRY_WAIT}:
            raise QueueError(f"job {job_id} is {current.status.value} and cannot be leased")
        leased = self.jobs.lease(WORKER_ID, now=self.jobs.clock(), lease_seconds=60)
        if leased is None:
            raise QueueError(f"job {job_id} is not available to lease")
        if leased.id != job_id:
            raise QueueError(
                f"leased {leased.id} instead of {job_id}; process queued previs in order"
            )
        return leased

    def _model_request(
        self, project_id: str, principal: Principal, acl_epoch: int, prompt: str
    ) -> ModelRequest:
        return ModelRequest(
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

    def _route_card(
        self, project_id: str, principal: Principal, acl_epoch: int, prompt: str
    ) -> Any:
        request = self._model_request(project_id, principal, acl_epoch, prompt)
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
            body="{{ disclaimer }}\n{{ continuity_limitations }}\n{{ prompt }}\n{{ router_text }}",
            principal=principal,
            acl_epoch=acl_epoch,
        )

        def mark(idx: dict[str, Any]) -> None:
            idx["template_ready"] = True

        mutate_index(self.workspace, mark)

    def _prompt_and_fingerprint(
        self,
        shot: StoredShot,
        storyboard_frame_id: str | None,
        regeneration_count: int,
    ) -> tuple[str, str]:
        camera = shot.record.camera
        prompt = "\n".join(
            [
                DISCLAIMER,
                CONTINUITY_LIMITATIONS,
                f"SHOT {shot.record.id}",
                f"STORYBOARD {storyboard_frame_id or 'none'}",
                f"CAMERA lens_mm={camera.lens_mm} sensor={camera.sensor} "
                f"movement={camera.movement} height_m={camera.height_m}",
                f"COLOR {shot.color_intent}",
                f"COMPOSITION {shot.record.composition_notes}",
                f"REGENERATION {regeneration_count}",
            ]
        )
        _, digest = digest_payload(
            {
                "shot_id": shot.record.id,
                "storyboard_frame_id": storyboard_frame_id,
                "camera": camera.to_dict(),
                "color_intent": shot.color_intent,
                "source_revision_id": self.revisions.canon_head_id(),
                "regeneration_count": regeneration_count,
            }
        )
        return prompt, digest

    def _require_consent(self, project_id: str) -> None:
        view = self.consent_view(project_id)
        if view.state is ConsentState.GRANTED:
            return
        raise ConsentRequiredError(
            f"video previs requires granted consent; current state is {view.state.value}"
        )

    def _clip_for_fingerprint(self, project_id: str, fingerprint: str) -> VideoClip | None:
        index = load_index(self.workspace)
        clip_id = dict(index.get("by_fingerprint", {})).get(fingerprint)
        if clip_id is None:
            return None
        digest = dict(index.get("clip_digests", {})).get(str(clip_id))
        if digest is None:
            return None
        stored = VideoClip.from_dict(load_payload(self.workspace, str(digest)))
        if stored.project_id != project_id:
            return None
        return stored

    def _with_freshness(
        self, stored: VideoClip, principal: Principal, acl_epoch: int
    ) -> VideoClip:
        shot = self.shots.get_shot(stored.shot_id, principal=principal, acl_epoch=acl_epoch)
        if shot.labeled_stale == stored.labeled_stale:
            return stored
        updated = VideoClip(
            id=stored.id,
            project_id=stored.project_id,
            shot_id=stored.shot_id,
            job_id=stored.job_id,
            source_revision_id=stored.source_revision_id,
            prompt=stored.prompt,
            input_fingerprint=stored.input_fingerprint,
            estimated_cost_low=stored.estimated_cost_low,
            estimated_cost_high=stored.estimated_cost_high,
            storyboard_frame_id=stored.storyboard_frame_id,
            artifact_id=stored.artifact_id,
            artifact_version_id=stored.artifact_version_id,
            provenance=dict(stored.provenance or {}),
            actual_cost=stored.actual_cost,
            accepted=stored.accepted,
            labeled_stale=shot.labeled_stale,
            video_provider_used=stored.video_provider_used,
            reused_accepted_asset=stored.reused_accepted_asset,
            labeled_previs=True,
            canon=False,
            regeneration_count=stored.regeneration_count,
            parent_id=stored.parent_id,
        )
        return self._put_clip(updated)

    def _load_clip(self, clip_id: str) -> VideoClip:
        index = load_index(self.workspace)
        digest = dict(index.get("clip_digests", {})).get(clip_id)
        if digest is None:
            raise ClipNotFoundError(f"previs clip {clip_id} is not in the index")
        return VideoClip.from_dict(load_payload(self.workspace, str(digest)))

    def _load_timeline(self, timeline_id: str) -> PrevisTimeline:
        index = load_index(self.workspace)
        digest = dict(index.get("timeline_digests", {})).get(timeline_id)
        if digest is None:
            raise TimelineNotFoundError(f"previs timeline {timeline_id} is not in the index")
        return PrevisTimeline.from_dict(load_payload(self.workspace, str(digest)))

    def _put_clip(self, stored: VideoClip) -> VideoClip:
        def persist(index: dict[str, Any]) -> VideoClip:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("clip_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["clip_ids"] = ids
            digests = dict(index.get("clip_digests", {}))
            digests[stored.id] = digest
            index["clip_digests"] = digests
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
            fingerprints[stored.input_fingerprint] = stored.id
            index["by_fingerprint"] = fingerprints
            by_job = dict(index.get("by_job", {}))
            by_job[stored.job_id] = stored.id
            index["by_job"] = by_job
            return stored

        return mutate_index(self.workspace, persist)

    def _put_timeline(self, stored: PrevisTimeline) -> PrevisTimeline:
        def persist(index: dict[str, Any]) -> PrevisTimeline:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("timeline_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["timeline_ids"] = ids
            digests = dict(index.get("timeline_digests", {}))
            digests[stored.id] = digest
            index["timeline_digests"] = digests
            return stored

        return mutate_index(self.workspace, persist)

    def _put_review(self, stored: IntendedEffectReview) -> IntendedEffectReview:
        def persist(index: dict[str, Any]) -> IntendedEffectReview:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("review_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["review_ids"] = ids
            digests = dict(index.get("review_digests", {}))
            digests[stored.id] = digest
            index["review_digests"] = digests
            return stored

        return mutate_index(self.workspace, persist)

    def _put_consent(self, stored: ConsentRecord) -> ConsentRecord:
        def persist(index: dict[str, Any]) -> ConsentRecord:
            consent = dict(index.get("consent", {}))
            consent[stored.project_id] = {
                "state": stored.state.value,
                "actor_id": stored.actor_id,
                "decided_at": stored.decided_at,
            }
            index["consent"] = consent
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
            object_kind="video_previs",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
