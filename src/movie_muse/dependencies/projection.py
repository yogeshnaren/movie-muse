"""Current/stale UI projections. Stale nodes are labeled and never current."""

from __future__ import annotations

from movie_muse.dependencies.types import NodeState, NodeView, StoredNode


def view_from_stored(node: StoredNode) -> NodeView:
    stale = node.state is NodeState.STALE
    return NodeView(
        id=node.id,
        project_id=node.project_id,
        kind=node.kind,
        state=node.state,
        current=not stale,
        labeled_stale=stale,
        input_ids=node.record.input_ids,
        input_hashes=node.record.input_hashes,
        content_hash=node.content_hash,
        config_hash=node.config_hash,
        model_hash=node.model_hash,
        code_version=node.record.code_version,
        schema_version=node.record.schema_version,
        model_version=node.record.model_version,
        provider_version=node.provider_version,
        prompt_template_version=node.record.prompt_template_version,
        rights_snapshot_id=node.record.rights_snapshot_id,
        produced_at=node.record.produced_at,
        subject_id=node.subject_id,
        queued_job_id=node.queued_job_id,
    )


def render_node_text(view: NodeView) -> str:
    freshness = "stale (not current)" if view.state is NodeState.STALE else "current"
    return (
        f"{view.kind.value} {view.id} state={view.state.value} "
        f"current={str(view.current).lower()} labeled_stale={str(view.labeled_stale).lower()} "
        f"freshness={freshness} produced_at={view.produced_at}"
    )


def render_node_html(view: NodeView) -> str:
    """Accessible labeled projection. Stale nodes never get current semantics."""

    state_value = view.state.value
    aria_current = "false" if view.state is NodeState.STALE else "true"
    label = (
        '<p class="stale-label" data-current="false">Stale — not current</p>'
        if view.labeled_stale
        else '<p class="current-label">Current</p>'
    )
    return (
        f'<article class="dependency-node" data-state="{state_value}" '
        f'data-current="{str(view.current).lower()}" aria-current="{aria_current}" '
        f'data-node-id="{view.id}">'
        f"<h2>{view.kind.value}</h2>"
        f"{label}"
        f"<p>produced_at {view.produced_at}</p>"
        "</article>"
    )


def render_graph_html(views: tuple[NodeView, ...]) -> str:
    body = "".join(render_node_html(view) for view in views)
    return f'<section class="dependency-graph">{body}</section>'
