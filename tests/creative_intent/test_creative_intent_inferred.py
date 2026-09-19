"""AI suggestions stay inferred until an explicit human accept."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.creative_intent.api import (
    IntentAction,
    IntentKind,
    IntentLockError,
    IntentOrigin,
    IntentScope,
    IntentSourceRole,
)
from movie_muse.identity.api import Role, make_human_actor


def _invite_role(stack, role: Role):
    actor = make_human_actor(organization_id=stack.project.organization_id, display_name=role.value)
    stack.identity.register_actor(actor)
    invitation = stack.identity.invite(
        inviter_actor_id=stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=stack.project.id,
        role=role,
    )
    stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    return stack.identity.principal(actor.id)


def test_inferred_suggestion_cannot_lock_or_self_promote(intent_stack) -> None:
    suggestion = intent_stack.intents.suggest(
        intent_stack.intents.command(
            action=IntentAction.SET,
            kind=IntentKind.AUDIENCE_EXPERIENCE,
            scope=IntentScope.SCENE,
            scope_target_id=intent_stack.kitchen_id,
            statement="Audience should feel the lock before Ada speaks.",
            source_role=IntentSourceRole.WRITER,
            origin=IntentOrigin.CHAT,
            expected_revision_id=intent_stack.head,
            branch_id=intent_stack.branch_id,
            project_id=intent_stack.project.id,
            confidence=0.42,
        ),
        principal=intent_stack.principal,
        acl_epoch=intent_stack.epoch,
    )
    assert suggestion.is_inferred is True
    assert suggestion.intent.is_locked is False
    assert suggestion.intent.source_role is IntentSourceRole.INFERRED
    with pytest.raises(IntentLockError):
        intent_stack.intents.apply(
            intent_stack.intents.command(
                action=IntentAction.LOCK,
                kind=IntentKind.AUDIENCE_EXPERIENCE,
                scope=IntentScope.SCENE,
                scope_target_id=intent_stack.kitchen_id,
                statement=suggestion.intent.statement,
                source_role=IntentSourceRole.INFERRED,
                origin=IntentOrigin.CHAT,
                expected_revision_id=intent_stack.head,
                branch_id=intent_stack.branch_id,
                project_id=intent_stack.project.id,
                is_locked=True,
            ),
            principal=intent_stack.principal,
            acl_epoch=intent_stack.epoch,
        )
    stated, inferred = intent_stack.intents.stated_and_inferred(intent_stack.branch_id)
    assert not stated
    assert inferred and inferred[0].intent.id == suggestion.intent.id
    accepted = intent_stack.intents.accept_suggestion(
        suggestion.intent.id,
        principal=intent_stack.principal,
        acl_epoch=intent_stack.epoch,
    )
    assert accepted.intent.source_role is IntentSourceRole.WRITER
    assert accepted.intent.id != suggestion.intent.id
    assert accepted.evolves_from_id == suggestion.intent.id
    historic = intent_stack.intents.get(suggestion.intent.id)
    assert historic.envelope.is_inferred is True
    assert historic.active is False
    stated, inferred = intent_stack.intents.stated_and_inferred(intent_stack.branch_id)
    assert stated and stated[0].intent.source_role is IntentSourceRole.WRITER
    assert not inferred


def test_viewer_cannot_write_intent(intent_stack) -> None:
    viewer = _invite_role(intent_stack, Role.VIEWER)
    with pytest.raises(AuthorizationError):
        intent_stack.intents.apply(
            intent_stack.intents.command(
                action=IntentAction.SET,
                kind=IntentKind.TONE,
                scope=IntentScope.FILM,
                scope_target_id=intent_stack.project.id,
                statement="Make it funnier.",
                source_role=IntentSourceRole.WRITER,
                origin=IntentOrigin.CHAT,
                expected_revision_id=intent_stack.head,
                branch_id=intent_stack.branch_id,
                project_id=intent_stack.project.id,
            ),
            principal=viewer,
            acl_epoch=intent_stack.epoch,
        )
