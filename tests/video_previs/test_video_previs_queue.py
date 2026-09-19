"""Consent, durable queue, retry, cancel, cache reuse, and live-provider fail-closed."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Role, make_integration_actor
from movie_muse.jobs.api import JobStatus
from movie_muse.video_previs.api import (
    CONTINUITY_LIMITATIONS,
    DISCLAIMER,
    VIDEO_PROVIDER_ENV,
    ConsentRequiredError,
    VideoPrevisAcceptError,
    VideoProviderUnavailableError,
)


def test_enqueue_without_consent_fails_closed(previs_stack, stored_shot) -> None:
    with pytest.raises(ConsentRequiredError, match="granted consent"):
        previs_stack.previs.enqueue_clip(
            stored_shot.record.id,
            principal=previs_stack.principal,
            acl_epoch=previs_stack.epoch,
        )


def test_preflight_cost_range_does_not_enqueue(previs_stack, stored_shot) -> None:
    quote = previs_stack.previs.preflight(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    assert quote.low <= quote.estimated_cost <= quote.high
    assert quote.quote_id
    assert previs_stack.previs.list_clips(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    ) == ()


def test_enqueue_is_idempotent_and_durable(previs_stack, stored_shot) -> None:
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    first = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    second = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    assert first.id == second.id
    assert first.job_id == second.job_id
    assert first.job_id.startswith("job_")
    job = previs_stack.previs.job_for(
        first.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    assert job.status is JobStatus.QUEUED
    assert job.id == first.job_id


def test_accepted_asset_is_reused_on_identical_enqueue(previs_stack, stored_shot) -> None:
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    first = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    completed = previs_stack.previs.complete_local(
        first.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    accepted = previs_stack.previs.accept_clip(
        completed.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    reused = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    assert reused.id == accepted.id
    assert reused.reused_accepted_asset is True
    assert reused.artifact_version_id == accepted.artifact_version_id
    assert reused.canon is False


def test_provider_failure_is_durable_and_retryable(previs_stack, stored_shot) -> None:
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    clip = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    failed = previs_stack.previs.record_provider_failure(
        clip.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
        error="veo timeout",
        retryable=True,
    )
    assert failed.status is JobStatus.RETRY_WAIT
    assert failed.id == clip.job_id
    previs_stack.clock.advance(2)
    completed = previs_stack.previs.complete_local(
        clip.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    job = previs_stack.previs.job_for(
        completed.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    assert job.status is JobStatus.COMPLETED
    assert completed.artifact_id.startswith("art_")
    assert previs_stack.previs.progress(
        completed.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    ) == 1.0


def test_cancel_is_durable(previs_stack, stored_shot) -> None:
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    clip = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    canceled = previs_stack.previs.cancel_clip(
        clip.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    assert canceled.status is JobStatus.CANCELED
    assert canceled.canceled_by == previs_stack.owner.id


def test_withdrawn_consent_blocks_complete(previs_stack, stored_shot) -> None:
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    clip = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    previs_stack.previs.withdraw_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    with pytest.raises(ConsentRequiredError, match="withdrawn"):
        previs_stack.previs.complete_local(
            clip.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
        )


def test_live_video_provider_unset_fails_closed(
    previs_stack, stored_shot, monkeypatch
) -> None:
    monkeypatch.delenv(VIDEO_PROVIDER_ENV, raising=False)
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    clip = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    with pytest.raises(VideoProviderUnavailableError, match="unset"):
        previs_stack.previs.live_render(
            clip.id,
            principal=previs_stack.principal,
            acl_epoch=previs_stack.epoch,
        )


def test_live_video_provider_env_still_does_not_claim_the_gate(
    previs_stack, stored_shot, monkeypatch
) -> None:
    monkeypatch.setenv(VIDEO_PROVIDER_ENV, "https://video.example.invalid/v1")
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    clip = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    with pytest.raises(VideoProviderUnavailableError, match="stays NOT_RUN"):
        previs_stack.previs.live_render(
            clip.id,
            principal=previs_stack.principal,
            acl_epoch=previs_stack.epoch,
        )
    assert clip.video_provider_used is False


def test_integration_cannot_grant_or_accept(previs_stack, stored_shot) -> None:
    actor = make_integration_actor(
        organization_id=previs_stack.project.organization_id,
        display_name="Previs Bot",
    )
    previs_stack.identity.register_actor(actor)
    bot = previs_stack.identity.principal(actor.id)
    with pytest.raises(ConsentRequiredError, match="human"):
        previs_stack.previs.grant_consent(
            previs_stack.project.id,
            principal=bot,
            acl_epoch=previs_stack.identity.acl_epoch(),
        )
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    clip = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    completed = previs_stack.previs.complete_local(
        clip.id, principal=previs_stack.principal, acl_epoch=previs_stack.epoch
    )
    with pytest.raises(VideoPrevisAcceptError, match="human"):
        previs_stack.previs.accept_clip(
            completed.id, principal=bot, acl_epoch=previs_stack.identity.acl_epoch()
        )


def test_viewer_cannot_enqueue(previs_stack, stored_shot, member) -> None:
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    viewer = member(Role.VIEWER)
    with pytest.raises(AuthorizationError):
        previs_stack.previs.enqueue_clip(
            stored_shot.record.id,
            principal=viewer,
            acl_epoch=previs_stack.epoch,
        )


def test_disclaimer_and_continuity_limitations(previs_stack, stored_shot) -> None:
    previs_stack.previs.grant_consent(
        previs_stack.project.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    clip = previs_stack.previs.enqueue_clip(
        stored_shot.record.id,
        principal=previs_stack.principal,
        acl_epoch=previs_stack.epoch,
    )
    assert DISCLAIMER in clip.prompt
    assert CONTINUITY_LIMITATIONS in clip.prompt
    assert "not the finished film" in clip.disclaimer
    assert clip.labeled_previs is True
    assert clip.canon is False
