"""Pure DAG algorithms for frontiers, closures, cycles, and topo order."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping, Sequence

from movie_muse.dependencies.types import InputHashes, NodeState, StoredNode
from movie_muse.persistence.api import digest_payload
from movie_muse.schemas.api import DependencyNode

Adjacency = Mapping[str, tuple[str, ...]]


def outgoing_from_pairs(pairs: Iterable[tuple[str, str]]) -> dict[str, tuple[str, ...]]:
    buckets: dict[str, list[str]] = {}
    for src, dst in pairs:
        bucket = buckets.setdefault(src, [])
        if dst not in bucket:
            bucket.append(dst)
    return {src: tuple(dsts) for src, dsts in buckets.items()}


def frontier_of(outgoing: Adjacency, changed_ids: Iterable[str]) -> frozenset[str]:
    """Minimal invalidation frontier: nodes that directly consume changed inputs."""

    frontier: set[str] = set()
    for node_id in changed_ids:
        frontier.update(outgoing.get(node_id, ()))
    return frozenset(frontier)


def dependent_closure(outgoing: Adjacency, changed_ids: Iterable[str]) -> frozenset[str]:
    """Transitive dependents of ``changed_ids``, not including the changed roots."""

    seen: set[str] = set()
    stack = list(changed_ids)
    while stack:
        current = stack.pop()
        for dependent in outgoing.get(current, ()):
            if dependent not in seen:
                seen.add(dependent)
                stack.append(dependent)
    return frozenset(seen)


def stale_closure_from_scratch(outgoing: Adjacency, changed_ids: Iterable[str]) -> frozenset[str]:
    """Full DAG walk used as the oracle for incremental invalidation."""

    return dependent_closure(outgoing, changed_ids)


def reaches(outgoing: Adjacency, start: str, target: str) -> bool:
    if start == target:
        return True
    return target in dependent_closure(outgoing, [start])


def would_create_cycle(outgoing: Adjacency, from_id: str, to_id: str) -> bool:
    """True when adding ``from_id -> to_id`` (producer to consumer) would cycle."""

    if from_id == to_id:
        return True
    return reaches(outgoing, to_id, from_id)


def topological_order(outgoing: Adjacency, node_ids: Iterable[str]) -> tuple[str, ...]:
    """Kahn order over ``node_ids`` using only edges inside that set."""

    selected = set(node_ids)
    incoming_count = {node_id: 0 for node_id in selected}
    local_out: dict[str, list[str]] = {node_id: [] for node_id in selected}
    for src in selected:
        for dst in outgoing.get(src, ()):
            if dst in selected:
                local_out[src].append(dst)
                incoming_count[dst] += 1
    queue = deque(sorted(node_id for node_id, count in incoming_count.items() if count == 0))
    ordered: list[str] = []
    while queue:
        node_id = queue.popleft()
        ordered.append(node_id)
        for dst in local_out[node_id]:
            incoming_count[dst] -= 1
            if incoming_count[dst] == 0:
                queue.append(dst)
    if len(ordered) != len(selected):
        remaining = sorted(selected.difference(ordered))
        raise ValueError(f"cycle in subgraph: {remaining}")
    return tuple(ordered)


def output_identity(node: StoredNode) -> str:
    _, digest = digest_payload(
        {
            "id": node.id,
            "content_hash": node.content_hash,
            "config_hash": node.config_hash,
            "model_hash": node.model_hash,
            "code_version": node.record.code_version,
            "schema_version": node.record.schema_version,
            "model_version": node.record.model_version,
            "provider_version": node.provider_version,
            "prompt_template_version": node.record.prompt_template_version,
            "rights_snapshot_id": node.record.rights_snapshot_id,
        }
    )
    return digest


def compose_derived_hashes(upstreams: Sequence[StoredNode]) -> InputHashes:
    """Deterministic content/config/model hashes from current upstream nodes."""

    input_ids = tuple(node.id for node in upstreams)
    input_hashes = tuple(output_identity(node) for node in upstreams)
    _, content_hash = digest_payload({"kind": "content", "parts": [node.content_hash for node in upstreams]})
    _, config_hash = digest_payload({"kind": "config", "parts": [node.config_hash for node in upstreams]})
    _, model_hash = digest_payload({"kind": "model", "parts": [node.model_hash for node in upstreams]})
    if not upstreams:
        _, content_hash = digest_payload({"kind": "content", "parts": []})
        _, config_hash = digest_payload({"kind": "config", "parts": []})
        _, model_hash = digest_payload({"kind": "model", "parts": []})
    return InputHashes(
        content_hash=content_hash,
        config_hash=config_hash,
        model_hash=model_hash,
        input_ids=input_ids,
        input_hashes=input_hashes,
    )


def replace_node_state(
    node: StoredNode,
    *,
    state: NodeState,
    hashes: InputHashes | None = None,
    produced_at: str | None = None,
    queued_job_id: str | None | object = ...,
    generation: int | None = None,
) -> StoredNode:
    hashes = hashes or InputHashes(
        content_hash=node.content_hash,
        config_hash=node.config_hash,
        model_hash=node.model_hash,
        input_ids=node.record.input_ids,
        input_hashes=node.record.input_hashes,
    )
    record = DependencyNode(
        id=node.record.id,
        project_id=node.record.project_id,
        node_type=node.kind.value,
        input_ids=hashes.input_ids,
        input_hashes=hashes.input_hashes,
        code_version=node.record.code_version,
        produced_at=produced_at or node.record.produced_at,
        schema_version=node.record.schema_version,
        model_version=node.record.model_version,
        prompt_template_version=node.record.prompt_template_version,
        rights_snapshot_id=node.record.rights_snapshot_id,
        is_stale=state is NodeState.STALE,
    )
    queued: str | None
    if queued_job_id is ...:
        queued = node.queued_job_id
    else:
        queued = queued_job_id if isinstance(queued_job_id, str) else None
    return StoredNode(
        record=record,
        kind=node.kind,
        state=state,
        content_hash=hashes.content_hash,
        config_hash=hashes.config_hash,
        model_hash=hashes.model_hash,
        provider_version=node.provider_version,
        subject_id=node.subject_id,
        queued_job_id=queued,
        generation=node.generation if generation is None else generation,
    )
