"""Stale revision fail-closed, rebind, branch fork, and merge conflicts."""

from __future__ import annotations

from dataclasses import replace

import pytest

from movie_muse.compiler.api import CompilerService
from movie_muse.creative_intent.api import (
    IntentAction,
    IntentKind,
    IntentMergeConflictError,
    IntentOrigin,
    IntentScope,
    IntentScopeError,
    IntentSourceRole,
    StaleIntentError,
)
from movie_muse.film_ir.api import FilmIrService


def test_stale_head_is_fail_closed_then_rebind(intent_stack) -> None:
    first = intent_stack.intents.apply(
        intent_stack.intents.command(
            action=IntentAction.SET,
            kind=IntentKind.INFORMATION_STRATEGY,
            scope=IntentScope.SCENE,
            scope_target_id=intent_stack.kitchen_id,
            statement="Reveal the lock before the line.",
            source_role=IntentSourceRole.WRITER,
            origin=IntentOrigin.DIRECT,
            expected_revision_id=intent_stack.head,
            branch_id=intent_stack.branch_id,
            project_id=intent_stack.project.id,
        ),
        principal=intent_stack.principal,
        acl_epoch=intent_stack.epoch,
    )
    old_head = intent_stack.head
    document = intent_stack.revisions.replay_head()
    action = next(block for block in document.blocks if "lock" in block.text.lower())
    updated = replace(
        document,
        blocks=tuple(
            replace(block, text="Ada studies the lock twice.") if block.id == action.id else block
            for block in document.blocks
        ),
    )
    intent_stack.revisions.save_document(updated, actor_id=intent_stack.owner.id)
    new_head = intent_stack.head
    assert new_head != old_head
    record = intent_stack.intents.get(first.intent.id)
    assert record.stale is True
    with pytest.raises(StaleIntentError):
        intent_stack.intents.apply(
            intent_stack.intents.command(
                action=IntentAction.SET,
                kind=IntentKind.INFORMATION_STRATEGY,
                scope=IntentScope.SCENE,
                scope_target_id=intent_stack.kitchen_id,
                statement="Reveal later.",
                source_role=IntentSourceRole.WRITER,
                origin=IntentOrigin.CHAT,
                expected_revision_id=old_head,
                branch_id=intent_stack.branch_id,
                project_id=intent_stack.project.id,
            ),
            principal=intent_stack.principal,
            acl_epoch=intent_stack.epoch,
        )
    rebound = intent_stack.intents.rebind(
        first.intent.id,
        principal=intent_stack.principal,
        acl_epoch=intent_stack.epoch,
        expected_revision_id=new_head,
    )
    assert rebound.intent.revision_id == new_head
    assert intent_stack.intents.get(rebound.intent.id).stale is False


def test_branch_fork_and_merge_conflict(intent_stack) -> None:
    intent_stack.intents.apply(
        intent_stack.intents.command(
            action=IntentAction.SET,
            kind=IntentKind.POV,
            scope=IntentScope.FILM,
            scope_target_id=intent_stack.project.id,
            statement="Stay with Ada.",
            source_role=IntentSourceRole.WRITER,
            origin=IntentOrigin.DIRECT,
            expected_revision_id=intent_stack.head,
            branch_id=intent_stack.branch_id,
            project_id=intent_stack.project.id,
        ),
        principal=intent_stack.principal,
        acl_epoch=intent_stack.epoch,
    )
    side = intent_stack.revisions.create_branch("intent-explore", actor_id=intent_stack.owner.id)
    forked = intent_stack.intents.fork_to_branch(
        source_branch_id=intent_stack.branch_id,
        target_branch_id=side.id,
        principal=intent_stack.principal,
        acl_epoch=intent_stack.epoch,
        project_id=intent_stack.project.id,
    )
    assert forked and forked[0].intent.statement == "Stay with Ada."
    intent_stack.intents.apply(
        intent_stack.intents.command(
            action=IntentAction.SET,
            kind=IntentKind.POV,
            scope=IntentScope.FILM,
            scope_target_id=intent_stack.project.id,
            statement="Split POV with Ben.",
            source_role=IntentSourceRole.WRITER,
            origin=IntentOrigin.CHAT,
            expected_revision_id=intent_stack.head,
            branch_id=side.id,
            project_id=intent_stack.project.id,
        ),
        principal=intent_stack.principal,
        acl_epoch=intent_stack.epoch,
    )
    with pytest.raises(IntentMergeConflictError):
        intent_stack.intents.merge_from(
            source_branch_id=side.id,
            target_branch_id=intent_stack.branch_id,
            principal=intent_stack.principal,
            acl_epoch=intent_stack.epoch,
            project_id=intent_stack.project.id,
        )
    extra = intent_stack.intents.apply(
        intent_stack.intents.command(
            action=IntentAction.EXPLORE,
            kind=IntentKind.CHARACTER_INVARIANT,
            scope=IntentScope.SCENE,
            scope_target_id=intent_stack.kitchen_id,
            statement="Ada never explains the lock.",
            source_role=IntentSourceRole.WRITER,
            origin=IntentOrigin.DIRECT,
            expected_revision_id=intent_stack.head,
            branch_id=side.id,
            project_id=intent_stack.project.id,
        ),
        principal=intent_stack.principal,
        acl_epoch=intent_stack.epoch,
    )
    # Same-key POV still conflicts; isolate the unique key by merging a third branch.
    other = intent_stack.revisions.create_branch("intent-explore-2", actor_id=intent_stack.owner.id)
    intent_stack.intents.apply(
        intent_stack.intents.command(
            action=IntentAction.EXPLORE,
            kind=IntentKind.CHARACTER_INVARIANT,
            scope=IntentScope.SCENE,
            scope_target_id=intent_stack.kitchen_id,
            statement=extra.intent.statement,
            source_role=IntentSourceRole.WRITER,
            origin=IntentOrigin.DIRECT,
            expected_revision_id=intent_stack.head,
            branch_id=other.id,
            project_id=intent_stack.project.id,
        ),
        principal=intent_stack.principal,
        acl_epoch=intent_stack.epoch,
    )
    merged = intent_stack.intents.merge_from(
        source_branch_id=other.id,
        target_branch_id=intent_stack.branch_id,
        principal=intent_stack.principal,
        acl_epoch=intent_stack.epoch,
        project_id=intent_stack.project.id,
    )
    assert merged.clean
    assert merged.copied_ids
    keys = {record.envelope.kind for record in intent_stack.intents.list(intent_stack.branch_id)}
    assert IntentKind.CHARACTER_INVARIANT in keys


def test_scene_scope_validates_against_film_ir(intent_stack) -> None:
    compiler = CompilerService()
    film_ir = FilmIrService(intent_stack.workspace, compiler, intent_stack.authorization).project(
        intent_stack.revisions.replay_head(),
        principal=intent_stack.principal,
        acl_epoch=intent_stack.epoch,
    )
    with pytest.raises(IntentScopeError):
        intent_stack.intents.apply(
            intent_stack.intents.command(
                action=IntentAction.SET,
                kind=IntentKind.PERFORMANCE_RULE,
                scope=IntentScope.SCENE,
                scope_target_id="scn_not_in_film",
                statement="Hold the look.",
                source_role=IntentSourceRole.DIRECTOR,
                origin=IntentOrigin.DIRECT,
                expected_revision_id=intent_stack.head,
                branch_id=intent_stack.branch_id,
                project_id=intent_stack.project.id,
            ),
            principal=intent_stack.principal,
            acl_epoch=intent_stack.epoch,
            film_ir=film_ir,
        )
    ok = intent_stack.intents.apply(
        intent_stack.intents.command(
            action=IntentAction.VIOLATE,
            kind=IntentKind.PERFORMANCE_RULE,
            scope=IntentScope.SCENE,
            scope_target_id=film_ir.scene_order[0],
            statement="Break stillness only on the harbor cut.",
            source_role=IntentSourceRole.DIRECTOR,
            origin=IntentOrigin.DIRECT,
            expected_revision_id=intent_stack.head,
            branch_id=intent_stack.branch_id,
            project_id=intent_stack.project.id,
        ),
        principal=intent_stack.principal,
        acl_epoch=intent_stack.epoch,
        film_ir=film_ir,
    )
    assert ok.intent.scope_target_id == film_ir.scene_order[0]
