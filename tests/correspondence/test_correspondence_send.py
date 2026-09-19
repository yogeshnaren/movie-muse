"""Preview, approve, and fail-closed send for production correspondence."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.correspondence.api import PreviewRequiredError, SendNotAuthorizedError
from movie_muse.identity.api import Role, make_human_actor


def test_send_requires_preview_and_explicit_confirm(correspondence_stack) -> None:
    draft = correspondence_stack.correspondence.draft_message(
        project_id=correspondence_stack.project.id,
        recipients=("wardrobe@studio.test",),
        subject="Coat change",
        body="Hero coat is now navy.",
        principal=correspondence_stack.principal,
        acl_epoch=correspondence_stack.epoch,
    )
    with pytest.raises(PreviewRequiredError):
        correspondence_stack.correspondence.approve(
            draft.id,
            principal=correspondence_stack.principal,
            acl_epoch=correspondence_stack.epoch,
        )
    preview = correspondence_stack.correspondence.preview(
        draft.id,
        principal=correspondence_stack.principal,
        acl_epoch=correspondence_stack.epoch,
    )
    assert preview.recipients == ("wardrobe@studio.test",)
    assert preview.subject == "Coat change"
    assert "Hero coat is now navy." in preview.body
    assert "wardrobe@studio.test" in preview.content or "Coat change" in preview.content
    with pytest.raises(SendNotAuthorizedError):
        correspondence_stack.correspondence.send(
            draft.id,
            preview=preview,
            confirm=False,
            principal=correspondence_stack.principal,
            acl_epoch=correspondence_stack.epoch,
        )
    approved = correspondence_stack.correspondence.approve(
        draft.id,
        principal=correspondence_stack.principal,
        acl_epoch=correspondence_stack.epoch,
    )
    assert approved.approved is True
    result = correspondence_stack.correspondence.send(
        draft.id,
        preview=preview,
        confirm=True,
        principal=correspondence_stack.principal,
        acl_epoch=correspondence_stack.epoch,
    )
    assert result.network_sent is False
    assert result.delivery.recipient == "wardrobe@studio.test"
    assert result.delivery.channel == "email"


def test_send_rejects_mismatched_preview(correspondence_stack) -> None:
    draft = correspondence_stack.correspondence.draft_message(
        project_id=correspondence_stack.project.id,
        recipients=("wardrobe@studio.test",),
        subject="Coat change",
        body="Hero coat is now navy.",
        principal=correspondence_stack.principal,
        acl_epoch=correspondence_stack.epoch,
    )
    preview = correspondence_stack.correspondence.preview(
        draft.id,
        principal=correspondence_stack.principal,
        acl_epoch=correspondence_stack.epoch,
    )
    correspondence_stack.correspondence.approve(
        draft.id,
        principal=correspondence_stack.principal,
        acl_epoch=correspondence_stack.epoch,
    )
    mismatched = preview.__class__(
        draft_id=preview.draft_id,
        recipients=("other@studio.test",),
        subject=preview.subject,
        body=preview.body,
        content=preview.content,
        render_id=preview.render_id,
        checksum=preview.checksum,
        channel=preview.channel,
    )
    with pytest.raises(PreviewRequiredError):
        correspondence_stack.correspondence.send(
            draft.id,
            preview=mismatched,
            confirm=True,
            principal=correspondence_stack.principal,
            acl_epoch=correspondence_stack.epoch,
        )


def test_viewer_cannot_send(correspondence_stack) -> None:
    draft = correspondence_stack.correspondence.draft_message(
        project_id=correspondence_stack.project.id,
        recipients=("ad@studio.test",),
        subject="Call sheet",
        body="Day one sides attached.",
        principal=correspondence_stack.principal,
        acl_epoch=correspondence_stack.epoch,
    )
    preview = correspondence_stack.correspondence.preview(
        draft.id,
        principal=correspondence_stack.principal,
        acl_epoch=correspondence_stack.epoch,
    )
    correspondence_stack.correspondence.approve(
        draft.id,
        principal=correspondence_stack.principal,
        acl_epoch=correspondence_stack.epoch,
    )
    actor = make_human_actor(
        organization_id=correspondence_stack.project.organization_id, display_name="Viewer"
    )
    correspondence_stack.identity.register_actor(actor)
    invitation = correspondence_stack.identity.invite(
        inviter_actor_id=correspondence_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=correspondence_stack.project.id,
        role=Role.VIEWER,
    )
    correspondence_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    viewer = correspondence_stack.identity.principal(actor.id)
    epoch = correspondence_stack.identity.acl_epoch()
    with pytest.raises(AuthorizationError):
        correspondence_stack.correspondence.send(
            draft.id,
            preview=preview,
            confirm=True,
            principal=viewer,
            acl_epoch=epoch,
        )
