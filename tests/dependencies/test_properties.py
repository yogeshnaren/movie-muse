"""Property tests: incremental invalidation/recompute vs a clean full DAG walk."""

from __future__ import annotations

import random

from movie_muse.dependencies.api import (
    NodeKind,
    NodeState,
    dependent_closure,
    frontier_of,
    stale_closure_from_scratch,
    topological_order,
)
from movie_muse.persistence.api import digest_payload


def _build_random_graph(dep_stack, rng: random.Random) -> tuple[list[str], list[str]]:
    source_count = rng.randint(2, 4)
    derived_count = rng.randint(3, 8)
    sources: list[str] = []
    derived: list[str] = []
    for index in range(source_count):
        kind = rng.choice(
            [
                NodeKind.SOURCE_REVISION,
                NodeKind.CONFIGURATION,
                NodeKind.MODEL,
                NodeKind.ACCEPTED_CLAIM,
            ]
        )
        node = dep_stack.add_source(kind=kind, subject_id=f"src-{index}-{rng.randrange(1_000_000)}")
        sources.append(node.id)
    for _ in range(derived_count):
        pool = sources + derived
        width = rng.randint(1, min(2, len(pool)))
        upstreams = rng.sample(pool, k=width)
        kind = rng.choice([NodeKind.DERIVED_PROJECTION, NodeKind.ARTIFACT_VERSION])
        node = dep_stack.engine.add_node(
            project_id=dep_stack.project.id,
            kind=kind,
            principal=dep_stack.principal,
            acl_epoch=dep_stack.epoch,
            input_ids=upstreams,
        )
        derived.append(node.id)
    return sources, derived


def test_random_dags_incremental_invalidation_matches_full_walk(dep_stack) -> None:
    rng = random.Random(20260901)
    for trial in range(25):
        sources, derived = _build_random_graph(dep_stack, rng)
        changed = rng.sample(sources, k=rng.randint(1, len(sources)))
        for node_id in changed:
            _, digest = digest_payload({"trial": trial, "node": node_id, "nonce": rng.randrange(10**9)})
            dep_stack.engine.record_inputs(
                node_id,
                principal=dep_stack.principal,
                acl_epoch=dep_stack.epoch,
                content_hash=digest,
            )
        adj = dep_stack.engine.adjacency()
        result = dep_stack.engine.invalidate_inputs(
            changed, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
        )
        full = stale_closure_from_scratch(adj, changed)
        assert set(result.closure) == set(full)
        assert set(result.frontier) == set(frontier_of(adj, changed))
        assert set(result.closure) == set(dependent_closure(adj, changed))
        unchanged_derived = [node_id for node_id in derived if node_id not in full]
        for node_id in unchanged_derived:
            view = dep_stack.engine.view_node(
                node_id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
            )
            assert view.state is NodeState.CURRENT
            assert view.current is True
        for node_id in full:
            view = dep_stack.engine.view_node(
                node_id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
            )
            assert view.state is NodeState.STALE
            assert view.current is False
            assert view.labeled_stale is True
        # Reset this trial's derived/source nodes stay in the same workspace; next
        # trial adds more nodes. Isolation is by using only this trial's ids.


def test_incremental_recompute_matches_clean_full_recompute(dep_stack) -> None:
    rng = random.Random(20260911)
    sources, derived = _build_random_graph(dep_stack, rng)
    changed = rng.sample(sources, k=min(2, len(sources)))
    for node_id in changed:
        _, digest = digest_payload({"full": True, "node": node_id})
        dep_stack.engine.record_inputs(
            node_id,
            principal=dep_stack.principal,
            acl_epoch=dep_stack.epoch,
            content_hash=digest,
        )
    adj = dep_stack.engine.adjacency()
    closure = dependent_closure(adj, changed)
    dep_stack.engine.invalidate_inputs(
        changed, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    incremental = dep_stack.engine.recompute_nodes(
        topological_order(adj, closure),
        principal=dep_stack.principal,
        acl_epoch=dep_stack.epoch,
    )
    assert incremental
    incremental_views = {
        node_id: dep_stack.engine.view_node(
            node_id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
        )
        for node_id in derived
    }

    full_order = topological_order(adj, derived)
    for node_id in full_order:
        dep_stack.engine.recompute_node(
            node_id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
        )
    for node_id in derived:
        full_view = dep_stack.engine.view_node(
            node_id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
        )
        incremental_view = incremental_views[node_id]
        assert full_view.state is NodeState.CURRENT
        assert incremental_view.state is NodeState.CURRENT
        assert full_view.input_hashes == incremental_view.input_hashes
        assert full_view.content_hash == incremental_view.content_hash
        assert full_view.config_hash == incremental_view.config_hash
        assert full_view.model_hash == incremental_view.model_hash
        assert full_view.current is True
        assert incremental_view.current is True
