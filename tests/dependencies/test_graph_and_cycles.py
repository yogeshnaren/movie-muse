"""Typed nodes/edges and fail-closed cycle prevention."""

from __future__ import annotations

import pytest

from movie_muse.dependencies.api import (
    CycleError,
    NodeKind,
    NodeKindError,
    NodeState,
    would_create_cycle,
)


def test_add_node_records_architecture_kinds_and_input_hashes(dep_stack) -> None:
    source = dep_stack.add_source(subject_id=dep_stack.document.base_revision_id)
    claim = dep_stack.add_source(kind=NodeKind.ACCEPTED_CLAIM)
    config = dep_stack.add_source(kind=NodeKind.CONFIGURATION)
    model = dep_stack.add_source(kind=NodeKind.MODEL, model_version="router-1")
    rights = dep_stack.add_source(kind=NodeKind.RIGHTS_RECORD, rights_snapshot_id="snap-1")
    projection = dep_stack.add_derived(
        [source.id, claim.id, config.id, model.id, rights.id],
        prompt_template_version="tmpl-1",
        model_version="router-1",
        provider_version="double-1",
        rights_snapshot_id="snap-1",
    )
    artifact = dep_stack.engine.add_node(
        project_id=dep_stack.project.id,
        kind=NodeKind.ARTIFACT_VERSION,
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
        input_ids=[projection.id],
    )
    view = dep_stack.engine.view_node(
        artifact.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert view.state is NodeState.CURRENT
    assert view.current is True
    assert view.labeled_stale is False
    assert view.input_ids == (projection.id,)
    assert view.code_version
    assert view.schema_version
    assert view.produced_at
    assert projection.record.model_version == "router-1"
    assert projection.record.prompt_template_version == "tmpl-1"
    assert projection.record.rights_snapshot_id == "snap-1"
    assert projection.provider_version == "double-1"


def test_cycle_rejected_leaves_graph_unchanged(dep_stack) -> None:
    a = dep_stack.add_source()
    b = dep_stack.add_derived([a.id])
    c = dep_stack.add_derived([b.id])
    with pytest.raises(CycleError, match="cycle"):
        dep_stack.engine.add_edge(
            from_id=c.id,
            to_id=a.id,
            principal=dep_stack.principal,
            acl_epoch=dep_stack.epoch,
        )
    adj = dep_stack.engine.adjacency()
    assert would_create_cycle(adj, c.id, a.id)
    assert a.id not in adj.get(c.id, ())
    view = dep_stack.engine.view_node(a.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch)
    assert view.state is NodeState.CURRENT


def test_self_edge_is_a_cycle(dep_stack) -> None:
    node = dep_stack.add_source()
    with pytest.raises(CycleError):
        dep_stack.engine.add_edge(
            from_id=node.id,
            to_id=node.id,
            principal=dep_stack.principal,
            acl_epoch=dep_stack.epoch,
        )


def test_duplicate_edge_is_idempotent(dep_stack) -> None:
    src = dep_stack.add_source()
    dst = dep_stack.add_source(kind=NodeKind.CONFIGURATION)
    first = dep_stack.engine.add_edge(
        from_id=src.id,
        to_id=dst.id,
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
    )
    second = dep_stack.engine.add_edge(
        from_id=src.id,
        to_id=dst.id,
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
    )
    assert first.id == second.id


def test_unknown_kind_fails_closed(dep_stack) -> None:
    with pytest.raises(NodeKindError):
        dep_stack.engine.add_node(
            project_id=dep_stack.project.id,
            kind="not_a_kind",
            principal=dep_stack.principal,
            acl_epoch=dep_stack.epoch,
        )
