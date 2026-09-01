"""Review, preview/export/delivery authorization, and fail-closed links."""

from __future__ import annotations

import pytest

from movie_muse.artifacts.api import (
    ArtifactClassification,
    ArtifactDeliveryError,
    ArtifactReviewError,
    ArtifactTemplateNotFoundError,
    ArtifactType,
    ArtifactVersionNotFoundError,
)
from movie_muse.authorization.api import (
    Action,
    AuthorizationError,
    Resource,
    ResourceKind,
)
from movie_muse.identity.api import Role, make_human_actor
from movie_muse.revisions.api import RevisionNotFoundError
from movie_muse.schemas.api import ArtifactStatus


def _member(stack, role: Role):
    actor = make_human_actor(
        organization_id=stack.project.organization_id,
        display_name=role.value,
    )
    stack.identity.register_actor(actor)
    invitation = stack.identity.invite(
        inviter_actor_id=stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=stack.project.id,
        role=role,
    )
    stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    return stack.identity.principal(actor.id)


def _artifact_and_version(stack):
    template = stack.artifacts.register_template(
        project_id=stack.project.id,
        template_id="tmpl_delivery",
        version="1",
        renderer_version="json/1",
        body="Approved material only",
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    artifact = stack.artifacts.create_artifact(
        project_id=stack.project.id,
        artifact_type=ArtifactType.DOCUMENT,
        title="Review packet",
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    version = stack.artifacts.create_version(
        artifact.id,
        inputs={"summary": "Creator reviewed"},
        source_revision_id=stack.revisions.canon_head_id(),
        template_id=template.id,
        template_version=template.version,
        renderer_version=template.renderer_version,
        classification=ArtifactClassification.RESTRICTED,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    return artifact, version


def test_generated_version_requires_review_and_investor_listing_hides_draft(
    artifact_stack,
) -> None:
    _artifact, version = _artifact_and_version(artifact_stack)

    assert version.status is ArtifactStatus.DRAFT
    assert artifact_stack.artifacts.investor_listing(
        artifact_stack.project.id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    ) == ()
    with pytest.raises(ArtifactReviewError):
        artifact_stack.artifacts.transition_review(
            version.version.id,
            ArtifactStatus.APPROVED,
            principal=artifact_stack.principal,
            acl_epoch=artifact_stack.epoch,
        )

    submitted = artifact_stack.artifacts.transition_review(
        version.version.id,
        ArtifactStatus.IN_REVIEW,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    approved = artifact_stack.artifacts.transition_review(
        version.version.id,
        ArtifactStatus.APPROVED,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )

    assert submitted.status is ArtifactStatus.IN_REVIEW
    assert approved.status is ArtifactStatus.APPROVED
    assert [item.version.id for item in artifact_stack.artifacts.investor_listing(
        artifact_stack.project.id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )] == [version.version.id]
    assert artifact_stack.artifacts.get_version(
        version.version.id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    ).record.version.status is ArtifactStatus.DRAFT


def test_export_and_delivery_require_export_acl_preview_and_confirmation(
    artifact_stack, tmp_path
) -> None:
    artifact, version = _artifact_and_version(artifact_stack)
    viewer = _member(artifact_stack, Role.VIEWER)
    preview = artifact_stack.artifacts.preview(
        version.version.id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )

    with pytest.raises(AuthorizationError):
        artifact_stack.artifacts.export_version(
            version.version.id,
            tmp_path / "viewer.json",
            principal=viewer,
            acl_epoch=artifact_stack.epoch,
        )
    with pytest.raises(AuthorizationError):
        artifact_stack.artifacts.update_version(
            version.version.id,
            checksum="forged",
            principal=viewer,
            acl_epoch=artifact_stack.epoch,
        )
    with pytest.raises(AuthorizationError):
        artifact_stack.artifacts.deliver(
            version.version.id,
            preview_render_id=preview.render.id,
            preview_checksum=preview.render.checksum,
            channel="email",
            recipient="investor@example.invalid",
            confirm=True,
            principal=viewer,
            acl_epoch=artifact_stack.epoch,
        )
    with pytest.raises(ArtifactDeliveryError):
        artifact_stack.artifacts.deliver(
            version.version.id,
            preview_render_id=preview.render.id,
            preview_checksum=preview.render.checksum,
            channel="email",
            recipient="investor@example.invalid",
            confirm=False,
            principal=artifact_stack.principal,
            acl_epoch=artifact_stack.epoch,
        )
    assert artifact_stack.artifacts.list_deliveries(
        artifact.id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    ) == ()

    exported = artifact_stack.artifacts.export_version(
        version.version.id,
        tmp_path / "owner" / "packet.json",
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    delivery = artifact_stack.artifacts.deliver(
        version.version.id,
        preview_render_id=preview.render.id,
        preview_checksum=preview.render.checksum,
        channel="email",
        recipient="investor@example.invalid",
        confirm=True,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )

    assert exported.read_bytes() == preview.content
    assert delivery.network_sent is False
    assert delivery.preview_checksum == version.version.checksum
    assert len(artifact_stack.artifacts.list_deliveries(
        artifact.id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )) == 1
    assert any(
        record.operation == "artifact_delivery_confirmed"
        for record in artifact_stack.audit.list_records()
    )


def test_links_validate_source_revision_and_creation_declares_acl_resource(
    artifact_stack,
) -> None:
    artifact, version = _artifact_and_version(artifact_stack)
    known = artifact_stack.authorization.authorize(
        artifact_stack.principal,
        Action.READ,
        Resource(
            kind=ResourceKind.ARTIFACT,
            id=artifact.id,
            organization_id=artifact_stack.project.organization_id,
            project_id=artifact_stack.project.id,
        ),
        acl_epoch=artifact_stack.epoch,
    )
    unknown = artifact_stack.authorization.authorize(
        artifact_stack.principal,
        Action.READ,
        Resource(
            kind=ResourceKind.ARTIFACT,
            id="art_unknown",
            organization_id=artifact_stack.project.organization_id,
            project_id=artifact_stack.project.id,
        ),
        acl_epoch=artifact_stack.epoch,
    )

    assert known.allowed
    assert unknown.denied and unknown.reason == "unknown_resource"
    link = artifact_stack.artifacts.link_to_revision(
        version.version.id,
        artifact_stack.revisions.canon_head_id(),
        relation="source_revision",
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    assert link.source_revision_id == version.version.source_revision_id
    assert link in artifact_stack.artifacts.list_links(
        artifact.id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    with pytest.raises(RevisionNotFoundError):
        artifact_stack.artifacts.link_to_revision(
            version.version.id,
            "rev_unknown",
            principal=artifact_stack.principal,
            acl_epoch=artifact_stack.epoch,
        )


def test_missing_template_unknown_version_and_airplane_mode_fail_or_work_locally(
    artifact_stack,
) -> None:
    artifact_stack.workspace.set_airplane_mode(True)
    artifact = artifact_stack.artifacts.create_artifact(
        project_id=artifact_stack.project.id,
        artifact_type=ArtifactType.MEDIA,
        title="Offline media metadata",
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    with pytest.raises(ArtifactTemplateNotFoundError):
        artifact_stack.artifacts.create_version(
            artifact.id,
            inputs={},
            source_revision_id=artifact_stack.revisions.canon_head_id(),
            template_id="tmpl_missing",
            template_version="1",
            renderer_version="json/1",
            classification=ArtifactClassification.INTERNAL,
            principal=artifact_stack.principal,
            acl_epoch=artifact_stack.epoch,
        )
    with pytest.raises(ArtifactVersionNotFoundError):
        artifact_stack.artifacts.get_version(
            "arv_unknown",
            principal=artifact_stack.principal,
            acl_epoch=artifact_stack.epoch,
        )

    template = artifact_stack.artifacts.register_template(
        project_id=artifact_stack.project.id,
        version="1",
        renderer_version="json/1",
        body="offline",
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    local_version = artifact_stack.artifacts.create_version(
        artifact.id,
        inputs={"network": "not required"},
        source_revision_id=artifact_stack.revisions.canon_head_id(),
        template_id=template.id,
        template_version=template.version,
        renderer_version=template.renderer_version,
        classification=ArtifactClassification.INTERNAL,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    assert local_version.version.checksum
