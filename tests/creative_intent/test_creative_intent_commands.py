"""Direct and chat surfaces write the same typed intent commands."""

from __future__ import annotations

import pytest

from movie_muse.creative_intent.api import (
    IntentAction,
    IntentKind,
    IntentLockError,
    IntentOrigin,
    IntentScope,
    IntentSourceRole,
)


def test_direct_and_chat_share_canonical_payload(intent_stack) -> None:
    shared = dict(
        action=IntentAction.PRESERVE,
        kind=IntentKind.THEME,
        scope=IntentScope.FILM,
        scope_target_id=intent_stack.project.id,
        statement="Keep the kitchen claustrophobic.",
        source_role=IntentSourceRole.WRITER,
        expected_revision_id=intent_stack.head,
        branch_id=intent_stack.branch_id,
        project_id=intent_stack.project.id,
        exceptions=("except the harbor night beat",),
        anti_rules=("no hidden-authority language",),
    )
    direct_cmd = intent_stack.intents.command(origin=IntentOrigin.DIRECT, **shared)
    chat_cmd = intent_stack.intents.command(origin=IntentOrigin.CHAT, **shared)
    assert direct_cmd.canonical_payload() == chat_cmd.canonical_payload()
    direct = intent_stack.intents.apply_direct(
        direct_cmd, principal=intent_stack.principal, acl_epoch=intent_stack.epoch
    )
    listed = intent_stack.intents.list(intent_stack.branch_id)
    assert listed[0].intent.statement == "Keep the kitchen claustrophobic."
    assert listed[0].intent.source_role is IntentSourceRole.WRITER
    assert listed[0].intent.is_locked is False
    assert listed[0].intent.exceptions == ("except the harbor night beat",)
    assert listed[0].envelope.origin is IntentOrigin.DIRECT
    chat = intent_stack.intents.apply_chat(
        intent_stack.intents.command(
            origin=IntentOrigin.CHAT,
            action=IntentAction.SET,
            kind=IntentKind.TONE,
            scope=IntentScope.SCENE,
            scope_target_id=intent_stack.kitchen_id,
            statement="Dry, clipped, no score swell.",
            source_role=IntentSourceRole.WRITER,
            expected_revision_id=intent_stack.head,
            branch_id=intent_stack.branch_id,
            project_id=intent_stack.project.id,
        ),
        principal=intent_stack.principal,
        acl_epoch=intent_stack.epoch,
    )
    assert chat.intent.scope is IntentScope.SCENE
    assert chat.origin is IntentOrigin.CHAT
    assert direct.intent.id != chat.intent.id


def test_all_scopes_and_kinds_are_creator_owned(intent_stack) -> None:
    targets = {
        IntentScope.FILM: intent_stack.project.id,
        IntentScope.SEQUENCE: intent_stack.sequence_id,
        IntentScope.SCENE: intent_stack.kitchen_id,
        IntentScope.BEAT: intent_stack.document.blocks[1].id,
    }
    for kind in IntentKind:
        for scope, target in targets.items():
            envelope = intent_stack.intents.apply(
                intent_stack.intents.command(
                    action=IntentAction.SET,
                    kind=kind,
                    scope=scope,
                    scope_target_id=target,
                    statement=f"{kind.value} at {scope.value}",
                    source_role=IntentSourceRole.DIRECTOR
                    if kind is IntentKind.VISUAL_RULE
                    else IntentSourceRole.WRITER,
                    origin=IntentOrigin.DIRECT,
                    expected_revision_id=intent_stack.head,
                    branch_id=intent_stack.branch_id,
                    project_id=intent_stack.project.id,
                ),
                principal=intent_stack.principal,
                acl_epoch=intent_stack.epoch,
            )
            assert envelope.intent.revision_id == intent_stack.head
            assert envelope.owner_actor_id == intent_stack.owner.id
    active = intent_stack.intents.list(intent_stack.branch_id)
    assert len(active) == len(IntentKind) * len(targets)


def test_lock_prevents_overwrite_until_unlock(intent_stack) -> None:
    cmd = intent_stack.intents.command(
        action=IntentAction.LOCK,
        kind=IntentKind.PLOT_INVARIANT,
        scope=IntentScope.FILM,
        scope_target_id=intent_stack.project.id,
        statement="Ada never opens the pantry for someone else.",
        source_role=IntentSourceRole.WRITER,
        origin=IntentOrigin.DIRECT,
        expected_revision_id=intent_stack.head,
        branch_id=intent_stack.branch_id,
        project_id=intent_stack.project.id,
        is_locked=True,
    )
    locked = intent_stack.intents.apply(
        cmd, principal=intent_stack.principal, acl_epoch=intent_stack.epoch
    )
    assert locked.intent.is_locked is True
    with pytest.raises(IntentLockError):
        intent_stack.intents.apply(
            intent_stack.intents.command(
                action=IntentAction.SET,
                kind=IntentKind.PLOT_INVARIANT,
                scope=IntentScope.FILM,
                scope_target_id=intent_stack.project.id,
                statement="Ada can open it.",
                source_role=IntentSourceRole.WRITER,
                origin=IntentOrigin.CHAT,
                expected_revision_id=intent_stack.head,
                branch_id=intent_stack.branch_id,
                project_id=intent_stack.project.id,
            ),
            principal=intent_stack.principal,
            acl_epoch=intent_stack.epoch,
        )
    unlocked = intent_stack.intents.apply(
        intent_stack.intents.command(
            action=IntentAction.UNLOCK,
            kind=IntentKind.PLOT_INVARIANT,
            scope=IntentScope.FILM,
            scope_target_id=intent_stack.project.id,
            statement=locked.intent.statement,
            source_role=IntentSourceRole.WRITER,
            origin=IntentOrigin.DIRECT,
            expected_revision_id=intent_stack.head,
            branch_id=intent_stack.branch_id,
            project_id=intent_stack.project.id,
        ),
        principal=intent_stack.principal,
        acl_epoch=intent_stack.epoch,
    )
    assert unlocked.intent.is_locked is False
    assert unlocked.evolves_from_id == locked.intent.id
