"""Minimal frontier and exact dependent-closure staleness."""

from __future__ import annotations

from movie_muse.dependencies.api import (
    NodeKind,
    NodeState,
    dependent_closure,
    frontier_of,
    stale_closure_from_scratch,
)
from movie_muse.persistence.api import digest_payload
from movie_muse.schemas.api import ChangeSet, ChangeSetOperation, OperationType, new_id


def _update_block_change_set(
    *,
    base_revision_id: str,
    actor_id: str,
    block_id: str,
    text: str,
) -> ChangeSet:
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=base_revision_id,
        author_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
        operations=(
            ChangeSetOperation(
                id="op-0",
                order=0,
                op_type=OperationType.UPDATE_BLOCK,
                target_id=block_id,
                payload={"text": text},
            ),
        ),
    )


def test_single_leaf_change_stales_only_dependents_not_siblings(dep_stack) -> None:
    left = dep_stack.add_source()
    right = dep_stack.add_source()
    left_child = dep_stack.add_derived([left.id])
    right_child = dep_stack.add_derived([right.id])
    _, new_hash = digest_payload({"content": "left-changed"})
    dep_stack.engine.record_inputs(
        left.id,
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
        content_hash=new_hash,
    )
    result = dep_stack.engine.invalidate_inputs(
        [left.id],
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
    )
    adj = dep_stack.engine.adjacency()
    assert set(result.frontier) == {left_child.id}
    assert set(result.closure) == {left_child.id}
    assert set(result.closure) == stale_closure_from_scratch(adj, [left.id])
    assert frontier_of(adj, [left.id]) == frozenset({left_child.id})
    left_view = dep_stack.engine.view_node(
        left.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    sibling = dep_stack.engine.view_node(
        right_child.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    child = dep_stack.engine.view_node(
        left_child.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    right_src = dep_stack.engine.view_node(
        right.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert left_view.state is NodeState.CURRENT
    assert right_src.state is NodeState.CURRENT
    assert sibling.state is NodeState.CURRENT
    assert sibling.current is True
    assert child.state is NodeState.STALE
    assert child.current is False
    assert child.labeled_stale is True


def test_diamond_graph_stales_both_branches_and_join(dep_stack) -> None:
    source = dep_stack.add_source()
    left = dep_stack.add_derived([source.id])
    right = dep_stack.add_derived([source.id])
    join = dep_stack.engine.add_node(
        project_id=dep_stack.project.id,
        kind=NodeKind.ARTIFACT_VERSION,
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
        input_ids=[left.id, right.id],
    )
    _, new_hash = digest_payload({"content": "diamond-changed"})
    dep_stack.engine.record_inputs(
        source.id,
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
        content_hash=new_hash,
    )
    result = dep_stack.engine.invalidate_inputs(
        [source.id],
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
    )
    expected = {left.id, right.id, join.id}
    assert set(result.frontier) == {left.id, right.id}
    assert set(result.closure) == expected
    assert set(result.closure) == set(
        dep_stack.engine.dependent_closure_of(
            [source.id], principal=dep_stack.principal, acl_epoch=dep_stack.epoch
        )
    )
    adj = dep_stack.engine.adjacency()
    assert dependent_closure(adj, [source.id]) == expected
    for node_id in expected:
        view = dep_stack.engine.view_node(
            node_id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
        )
        assert view.state is NodeState.STALE
        assert view.current is False
        assert view.labeled_stale is True
    source_view = dep_stack.engine.view_node(
        source.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert source_view.state is NodeState.CURRENT


def test_accepted_change_set_invalidates_revision_dependents(dep_stack) -> None:
    head = dep_stack.revisions.canon_head_id()
    source = dep_stack.add_source(subject_id=head)
    projection = dep_stack.add_derived([source.id])
    artifact = dep_stack.engine.add_node(
        project_id=dep_stack.project.id,
        kind=NodeKind.ARTIFACT_VERSION,
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
        input_ids=[projection.id],
    )
    change = _update_block_change_set(
        base_revision_id=head,
        actor_id=dep_stack.owner.id,
        block_id=dep_stack.document.blocks[-1].id,
        text="Ada redraws the edges after the patch.",
    )
    ack = dep_stack.revisions.apply_change_set(change, actor_id=dep_stack.owner.id)
    result = dep_stack.engine.invalidate_for_change_set(
        change,
        result_revision_id=ack.revision_id,
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
        result_digest=ack.blob_digest,
        project_id=dep_stack.project.id,
    )
    assert projection.id in result.closure
    assert artifact.id in result.closure
    proj_view = dep_stack.engine.view_node(
        projection.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    art_view = dep_stack.engine.view_node(
        artifact.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert proj_view.state is NodeState.STALE
    assert art_view.state is NodeState.STALE
    assert proj_view.current is False
    listed = dep_stack.engine.list_nodes(
        dep_stack.project.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert any(item.subject_id == ack.revision_id for item in listed)
