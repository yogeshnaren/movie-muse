"""Stale nodes are viewable when labeled; export without override fails closed."""

from __future__ import annotations

import pytest

from movie_muse.dependencies.api import (
    NodeState,
    StaleExportDeniedError,
    compose_derived_hashes,
    render_node_html,
    render_node_text,
    topological_order,
)
from movie_muse.persistence.api import digest_payload


def test_recompute_makes_stale_node_current_with_matching_upstream_hashes(dep_stack) -> None:
    source = dep_stack.add_source()
    derived = dep_stack.add_derived([source.id])
    _, new_hash = digest_payload({"content": "recompute-me"})
    updated_source = dep_stack.engine.record_inputs(
        source.id,
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
        content_hash=new_hash,
    )
    dep_stack.engine.invalidate_inputs(
        [source.id], principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    stale = dep_stack.engine.view_node(
        derived.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert stale.state is NodeState.STALE
    assert stale.current is False
    result = dep_stack.engine.recompute_node(
        derived.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert result.state is NodeState.CURRENT
    assert result.skipped_upstream_stale is False
    current = dep_stack.engine.view_node(
        derived.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    expected = compose_derived_hashes([updated_source])
    assert current.state is NodeState.CURRENT
    assert current.current is True
    assert current.labeled_stale is False
    assert current.input_ids == (source.id,)
    assert current.input_hashes == expected.input_hashes
    assert current.content_hash == expected.content_hash
    assert current.config_hash == expected.config_hash
    assert current.model_hash == expected.model_hash


def test_recompute_blocked_while_upstream_stale(dep_stack) -> None:
    source = dep_stack.add_source()
    mid = dep_stack.add_derived([source.id])
    leaf = dep_stack.add_derived([mid.id])
    _, new_hash = digest_payload({"content": "blocked"})
    dep_stack.engine.record_inputs(
        source.id,
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
        content_hash=new_hash,
    )
    dep_stack.engine.invalidate_inputs(
        [source.id], principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    blocked = dep_stack.engine.recompute_node(
        leaf.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert blocked.state is NodeState.STALE
    assert blocked.skipped_upstream_stale is True
    dep_stack.engine.recompute_nodes(
        topological_order(dep_stack.engine.adjacency(), [mid.id, leaf.id]),
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
    )
    leaf_view = dep_stack.engine.view_node(
        leaf.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert leaf_view.state is NodeState.CURRENT


def test_stale_export_denied_without_override(dep_stack) -> None:
    source = dep_stack.add_source()
    derived = dep_stack.add_derived([source.id])
    _, new_hash = digest_payload({"content": "export-stale"})
    dep_stack.engine.record_inputs(
        source.id,
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
        content_hash=new_hash,
    )
    dep_stack.engine.invalidate_inputs(
        [source.id], principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    with pytest.raises(StaleExportDeniedError, match="override"):
        dep_stack.engine.export_node(
            derived.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
        )
    with pytest.raises(StaleExportDeniedError):
        dep_stack.engine.export_node(
            derived.id,
            principal=dep_stack.principal,
            acl_epoch=dep_stack.epoch,
            override=True,
            override_reason="   ",
        )


def test_stale_export_override_audits_and_stays_labeled_not_current(dep_stack) -> None:
    source = dep_stack.add_source()
    derived = dep_stack.add_derived([source.id])
    _, new_hash = digest_payload({"content": "override"})
    dep_stack.engine.record_inputs(
        source.id,
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
        content_hash=new_hash,
    )
    dep_stack.engine.invalidate_inputs(
        [source.id], principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    exported = dep_stack.engine.export_node(
        derived.id,
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
        override=True,
        override_reason="producer requested labeled stale sides",
    )
    assert exported.state is NodeState.STALE
    assert exported.current is False
    assert exported.labeled_stale is True
    assert exported.override is True
    assert exported.audit_record_id
    assert exported.payload["current"] is False
    assert exported.payload["state"] == "stale"
    records = dep_stack.audit.list_records()
    assert any(
        record.operation == "export_stale_override" and record.object_id == derived.id
        for record in records
    )


def test_current_export_does_not_require_override(dep_stack) -> None:
    source = dep_stack.add_source()
    exported = dep_stack.engine.export_node(
        source.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert exported.current is True
    assert exported.state is NodeState.CURRENT
    assert exported.override is False


def test_stale_ui_state_is_labeled_and_cannot_masquerade(dep_stack) -> None:
    source = dep_stack.add_source()
    derived = dep_stack.add_derived([source.id])
    _, new_hash = digest_payload({"content": "label-me"})
    dep_stack.engine.record_inputs(
        source.id,
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
        content_hash=new_hash,
    )
    dep_stack.engine.invalidate_inputs(
        [source.id], principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    view = dep_stack.engine.view_node(
        derived.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    html = render_node_html(view)
    text = render_node_text(view)
    page = dep_stack.engine.render_node(
        derived.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert view.current is False
    assert view.labeled_stale is True
    assert 'data-state="stale"' in html
    assert 'data-current="false"' in html
    assert 'aria-current="false"' in html
    assert "not current" in html.lower()
    assert 'data-state="current"' not in html
    assert "not current" in text
    assert 'data-state="stale"' in page
    graph = dep_stack.engine.render_graph(
        dep_stack.project.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert "dependency-graph" in graph
    assert "Stale — not current" in graph
