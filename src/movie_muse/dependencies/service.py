"""Permissioned dependency graph, invalidation frontier, and recompute queue."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import (
    Action,
    AuthContext,
    AuthorizationService,
)
from movie_muse.dependencies.errors import (
    CycleError,
    GraphIntegrityError,
    NodeKindError,
    NodeNotFoundError,
    StaleExportDeniedError,
)
from movie_muse.dependencies.graph import (
    compose_derived_hashes,
    dependent_closure,
    frontier_of,
    output_identity,
    replace_node_state,
    stale_closure_from_scratch,
    topological_order,
    would_create_cycle,
)
from movie_muse.dependencies.index import (
    adjacency,
    load_index,
    load_payload,
    mutate_index,
    put_payload,
)
from movie_muse.dependencies.projection import render_graph_html, render_node_html, view_from_stored
from movie_muse.dependencies.types import (
    CODE_VERSION,
    RECOMPUTE_JOB_TYPE,
    SCHEMA_VERSION,
    DependencyEdge,
    ExportRecord,
    InputHashes,
    InvalidationResult,
    NodeKind,
    NodeState,
    NodeView,
    RecomputeResult,
    StoredNode,
    parse_node_kind,
)
from movie_muse.identity.api import Principal
from movie_muse.jobs.api import Job, JobService
from movie_muse.persistence.api import LocalWorkspace, digest_payload, utc_now
from movie_muse.schemas.api import ChangeSet, DependencyNode, new_id, new_ulid, validate_payload


class DependencyEngine:
    """Typed dependency DAG with incremental invalidation and stale/current state."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        jobs: JobService,
        audit: AuditLog | None = None,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.jobs = jobs
        self.audit = audit or AuditLog(workspace)

    def add_node(
        self,
        *,
        project_id: str,
        kind: NodeKind | str,
        principal: Principal,
        acl_epoch: int,
        input_ids: Sequence[str] = (),
        content_hash: str | None = None,
        config_hash: str | None = None,
        model_hash: str | None = None,
        code_version: str = CODE_VERSION,
        schema_version: str = SCHEMA_VERSION,
        model_version: str | None = None,
        provider_version: str | None = None,
        prompt_template_version: str | None = None,
        rights_snapshot_id: str | None = None,
        subject_id: str | None = None,
        node_id: str | None = None,
    ) -> StoredNode:
        try:
            parsed = parse_node_kind(kind)
        except ValueError as exc:
            raise NodeKindError(str(exc)) from exc
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        minted = node_id or new_id("dependency_node")
        now = utc_now()
        _, default_content_hash = digest_payload(
            {"kind": "content", "node": minted, "subject": subject_id or ""}
        )
        _, default_config_hash = digest_payload({"kind": "config", "node": minted})
        _, default_model_hash = digest_payload({"kind": "model", "node": minted})

        def mutate(index: dict[str, Any]) -> StoredNode:
            if minted in index["node_digests"]:
                raise GraphIntegrityError(f"dependency node already exists: {minted}")
            if minted in {str(item) for item in input_ids}:
                raise CycleError(f"node {minted} cannot depend on itself")
            upstreams = [self._node(str(item), index) for item in input_ids]
            for upstream in upstreams:
                if upstream.project_id != project_id:
                    raise GraphIntegrityError("upstream node belongs to another project")
            if upstreams:
                hashes = compose_derived_hashes(upstreams)
                if content_hash is not None:
                    hashes = InputHashes(
                        content_hash=content_hash,
                        config_hash=config_hash or hashes.config_hash,
                        model_hash=model_hash or hashes.model_hash,
                        input_ids=hashes.input_ids,
                        input_hashes=hashes.input_hashes,
                    )
            else:
                hashes = InputHashes(
                    content_hash=content_hash or default_content_hash,
                    config_hash=config_hash or default_config_hash,
                    model_hash=model_hash or default_model_hash,
                    input_ids=(),
                    input_hashes=(),
                )
            record = DependencyNode(
                id=minted,
                project_id=project_id,
                node_type=parsed.value,
                input_ids=hashes.input_ids,
                input_hashes=hashes.input_hashes,
                code_version=code_version,
                produced_at=now,
                schema_version=schema_version,
                model_version=model_version,
                prompt_template_version=prompt_template_version,
                rights_snapshot_id=rights_snapshot_id,
                is_stale=False,
            )
            validate_payload("dependency_node", record.to_dict())
            stored = StoredNode(
                record=record,
                kind=parsed,
                state=NodeState.CURRENT,
                content_hash=hashes.content_hash,
                config_hash=hashes.config_hash,
                model_hash=hashes.model_hash,
                provider_version=provider_version,
                subject_id=subject_id,
            )
            self._put_node(index, stored)
            for upstream in upstreams:
                self._put_edge(
                    index,
                    DependencyEdge(
                        id=f"dpe_{new_ulid()}",
                        project_id=project_id,
                        from_id=upstream.id,
                        to_id=stored.id,
                        created_at=now,
                    ),
                )
            return stored

        return mutate_index(self.workspace, mutate)

    def add_edge(
        self,
        *,
        from_id: str,
        to_id: str,
        principal: Principal,
        acl_epoch: int,
    ) -> DependencyEdge:
        from_node = self._peek(from_id)
        self._require(principal, Action.PROPOSE, from_node.project_id, acl_epoch)
        now = utc_now()

        def mutate(index: dict[str, Any]) -> DependencyEdge:
            src = self._node(from_id, index)
            dst = self._node(to_id, index)
            if src.project_id != dst.project_id:
                raise GraphIntegrityError("edge endpoints must share a project")
            outgoing = adjacency(index)
            if would_create_cycle(outgoing, from_id, to_id):
                raise CycleError(f"edge {from_id} -> {to_id} would create a cycle")
            existing = self._find_edge(index, from_id, to_id)
            if existing is not None:
                return existing
            edge = DependencyEdge(
                id=f"dpe_{new_ulid()}",
                project_id=src.project_id,
                from_id=from_id,
                to_id=to_id,
                created_at=now,
            )
            self._put_edge(index, edge)
            if from_id not in dst.record.input_ids:
                hashes = InputHashes(
                    content_hash=dst.content_hash,
                    config_hash=dst.config_hash,
                    model_hash=dst.model_hash,
                    input_ids=(*dst.record.input_ids, from_id),
                    input_hashes=(*dst.record.input_hashes, output_identity(src)),
                )
                updated = replace_node_state(dst, state=NodeState.STALE, hashes=hashes)
                self._put_node(index, updated)
            return edge

        return mutate_index(self.workspace, mutate)

    def record_inputs(
        self,
        node_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        content_hash: str | None = None,
        config_hash: str | None = None,
        model_hash: str | None = None,
        input_ids: Sequence[str] | None = None,
        input_hashes: Sequence[str] | None = None,
    ) -> StoredNode:
        existing = self._peek(node_id)
        self._require(principal, Action.PROPOSE, existing.project_id, acl_epoch)

        def mutate(index: dict[str, Any]) -> StoredNode:
            node = self._node(node_id, index)
            ids = tuple(str(item) for item in (input_ids if input_ids is not None else node.record.input_ids))
            hashes_in = tuple(
                str(item)
                for item in (input_hashes if input_hashes is not None else node.record.input_hashes)
            )
            if len(ids) != len(hashes_in):
                raise GraphIntegrityError("input_ids and input_hashes must be the same length")
            hashes = InputHashes(
                content_hash=content_hash or node.content_hash,
                config_hash=config_hash or node.config_hash,
                model_hash=model_hash or node.model_hash,
                input_ids=ids,
                input_hashes=hashes_in,
            )
            state = NodeState.CURRENT
            if ids:
                upstreams = [self._node(item, index) for item in ids]
                expected = compose_derived_hashes(upstreams)
                matches = (
                    hashes.input_hashes == expected.input_hashes
                    and hashes.content_hash == expected.content_hash
                    and hashes.config_hash == expected.config_hash
                    and hashes.model_hash == expected.model_hash
                    and all(item.state is NodeState.CURRENT for item in upstreams)
                )
                state = NodeState.CURRENT if matches else NodeState.STALE
            updated = replace_node_state(
                node,
                state=state,
                hashes=hashes,
                produced_at=utc_now(),
            )
            self._put_node(index, updated)
            return updated

        return mutate_index(self.workspace, mutate)

    def compute_frontier(
        self,
        changed_ids: Sequence[str],
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> frozenset[str]:
        if changed_ids:
            probe = self._peek(str(changed_ids[0]))
            self._require(principal, Action.READ, probe.project_id, acl_epoch)
        return frontier_of(self.adjacency(), changed_ids)

    def dependent_closure_of(
        self,
        changed_ids: Sequence[str],
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> frozenset[str]:
        if changed_ids:
            probe = self._peek(str(changed_ids[0]))
            self._require(principal, Action.READ, probe.project_id, acl_epoch)
        return dependent_closure(self.adjacency(), changed_ids)

    def adjacency(self) -> dict[str, tuple[str, ...]]:
        return adjacency(load_index(self.workspace))

    def invalidate_inputs(
        self,
        changed_ids: Sequence[str],
        *,
        principal: Principal,
        acl_epoch: int,
        extra_frontier: Sequence[str] = (),
    ) -> InvalidationResult:
        if not changed_ids and not extra_frontier:
            return InvalidationResult((), (), (), (), int(load_index(self.workspace)["generation"]))
        probe = self._peek(str((changed_ids or extra_frontier)[0]))
        self._require(principal, Action.PROPOSE, probe.project_id, acl_epoch)
        planned = mutate_index(
            self.workspace,
            lambda index: self._plan_invalidation(index, changed_ids, extra_frontier),
        )
        jobs = self._enqueue_recompute(
            planned["closure"],
            project_id=probe.project_id,
            principal=principal,
            acl_epoch=acl_epoch,
            generation=int(planned["generation"]),
        )
        if jobs:
            job_by_node = {
                str(job_payload["node_id"]): job
                for job, job_payload in jobs
            }

            def attach(index: dict[str, Any]) -> None:
                for node_id, job in job_by_node.items():
                    node = self._node(node_id, index)
                    self._put_node(
                        index,
                        replace_node_state(node, state=node.state, queued_job_id=job.id),
                    )
                    index["queued"][node_id] = job.id

            mutate_index(self.workspace, attach)
        return InvalidationResult(
            changed_ids=tuple(str(item) for item in changed_ids),
            frontier=tuple(sorted(planned["frontier"])),
            closure=tuple(sorted(planned["closure"])),
            jobs=tuple(job for job, _payload in jobs),
            generation=int(planned["generation"]),
        )

    def invalidate_for_change_set(
        self,
        change_set: ChangeSet,
        *,
        result_revision_id: str,
        principal: Principal,
        acl_epoch: int,
        result_digest: str | None = None,
        project_id: str | None = None,
    ) -> InvalidationResult:
        index = load_index(self.workspace)
        changed: list[str] = []
        extra_frontier: list[str] = []
        tokens = {change_set.base_revision_id, result_revision_id}
        for node_id in index["node_ids"]:
            node = self._node(str(node_id), index)
            if project_id is not None and node.project_id != project_id:
                continue
            if node.subject_id in tokens or node.id in tokens:
                changed.append(node.id)
            if any(token in node.record.input_ids or token in node.record.input_hashes for token in tokens):
                extra_frontier.append(node.id)
        scoped_project = project_id
        if scoped_project is None and changed:
            scoped_project = self._peek(changed[0]).project_id
        if scoped_project is None and extra_frontier:
            scoped_project = self._peek(extra_frontier[0]).project_id
        if scoped_project is not None:
            self.add_node(
                project_id=scoped_project,
                kind=NodeKind.SOURCE_REVISION,
                principal=principal,
                acl_epoch=acl_epoch,
                subject_id=result_revision_id,
                content_hash=result_digest or result_revision_id,
            )
        if not changed and not extra_frontier:
            return InvalidationResult((), (), (), (), int(load_index(self.workspace)["generation"]))
        return self.invalidate_inputs(
            changed,
            principal=principal,
            acl_epoch=acl_epoch,
            extra_frontier=extra_frontier,
        )

    def mark_stale(
        self,
        node_ids: Sequence[str],
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[str, ...]:
        if not node_ids:
            return ()
        probe = self._peek(str(node_ids[0]))
        self._require(principal, Action.PROPOSE, probe.project_id, acl_epoch)

        def mutate(index: dict[str, Any]) -> tuple[str, ...]:
            marked: list[str] = []
            for node_id in node_ids:
                node = self._node(str(node_id), index)
                updated = replace_node_state(node, state=NodeState.STALE, queued_job_id=None)
                self._put_node(index, updated)
                marked.append(updated.id)
            return tuple(marked)

        return mutate_index(self.workspace, mutate)

    def recompute_node(
        self,
        node_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> RecomputeResult:
        existing = self._peek(node_id)
        self._require(principal, Action.PROPOSE, existing.project_id, acl_epoch)

        def mutate(index: dict[str, Any]) -> RecomputeResult:
            node = self._node(node_id, index)
            upstream_ids = node.record.input_ids
            upstreams = [self._node(item, index) for item in upstream_ids]
            if any(item.state is NodeState.STALE for item in upstreams):
                stale = replace_node_state(node, state=NodeState.STALE)
                self._put_node(index, stale)
                return RecomputeResult(
                    node_id=node.id,
                    state=NodeState.STALE,
                    input_hashes=InputHashes(
                        content_hash=stale.content_hash,
                        config_hash=stale.config_hash,
                        model_hash=stale.model_hash,
                        input_ids=stale.record.input_ids,
                        input_hashes=stale.record.input_hashes,
                    ),
                    produced_at=stale.record.produced_at,
                    skipped_upstream_stale=True,
                )
            hashes = compose_derived_hashes(upstreams) if upstreams else InputHashes(
                content_hash=node.content_hash,
                config_hash=node.config_hash,
                model_hash=node.model_hash,
                input_ids=node.record.input_ids,
                input_hashes=node.record.input_hashes,
            )
            current = replace_node_state(
                node,
                state=NodeState.CURRENT,
                hashes=hashes,
                produced_at=utc_now(),
                queued_job_id=None,
            )
            self._put_node(index, current)
            index["queued"].pop(node.id, None)
            return RecomputeResult(
                node_id=current.id,
                state=NodeState.CURRENT,
                input_hashes=hashes,
                produced_at=current.record.produced_at,
            )

        return mutate_index(self.workspace, mutate)

    def recompute_nodes(
        self,
        node_ids: Sequence[str],
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[RecomputeResult, ...]:
        ordered = topological_order(self.adjacency(), node_ids)
        return tuple(
            self.recompute_node(node_id, principal=principal, acl_epoch=acl_epoch)
            for node_id in ordered
        )

    def view_node(
        self,
        node_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> NodeView:
        node = self._peek(node_id)
        self._require(principal, Action.READ, node.project_id, acl_epoch)
        return view_from_stored(node)

    def list_nodes(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[NodeView, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        index = load_index(self.workspace)
        views: list[NodeView] = []
        for node_id in index["project_nodes"].get(project_id, []):
            views.append(view_from_stored(self._node(str(node_id), index)))
        return tuple(views)

    def export_node(
        self,
        node_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        override: bool = False,
        override_reason: str | None = None,
    ) -> ExportRecord:
        node = self._peek(node_id)
        view = view_from_stored(node)
        self._require(principal, Action.EXPORT, node.project_id, acl_epoch)
        if view.state is NodeState.STALE:
            if not override or not (override_reason or "").strip():
                raise StaleExportDeniedError(
                    f"stale node {node_id} cannot be exported without explicit override and audit"
                )
            audit = self.audit.append(
                actor_id=principal.actor_id,
                effective_principal_id=principal.actor_id,
                operation="export_stale_override",
                object_kind="dependency_node",
                object_id=node.id,
                policy_decision=PolicyDecision.ALLOW,
                acl_epoch=acl_epoch,
                reason=(override_reason or "").strip(),
            )
            payload = self._export_payload(view, override=True)
            return ExportRecord(
                node_id=view.id,
                state=NodeState.STALE,
                current=False,
                labeled_stale=True,
                override=True,
                payload=payload,
                audit_record_id=audit.id,
            )
        payload = self._export_payload(view, override=False)
        return ExportRecord(
            node_id=view.id,
            state=NodeState.CURRENT,
            current=True,
            labeled_stale=False,
            override=False,
            payload=payload,
        )

    def render_node(
        self,
        node_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> str:
        return render_node_html(self.view_node(node_id, principal=principal, acl_epoch=acl_epoch))

    def render_graph(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> str:
        return render_graph_html(self.list_nodes(project_id, principal=principal, acl_epoch=acl_epoch))

    def full_stale_set(self, changed_ids: Sequence[str]) -> frozenset[str]:
        return stale_closure_from_scratch(self.adjacency(), changed_ids)

    def _plan_invalidation(
        self,
        index: dict[str, Any],
        changed_ids: Sequence[str],
        extra_frontier: Sequence[str],
    ) -> dict[str, Any]:
        outgoing = adjacency(index)
        changed = tuple(str(item) for item in changed_ids)
        extra = frozenset(str(item) for item in extra_frontier)
        frontier = set(frontier_of(outgoing, changed))
        frontier.update(extra)
        closure = set(dependent_closure(outgoing, changed))
        closure.update(extra)
        closure.update(dependent_closure(outgoing, extra))
        generation = int(index["generation"]) + 1
        index["generation"] = generation
        for node_id in sorted(closure):
            node = self._node(node_id, index)
            self._put_node(
                index,
                replace_node_state(
                    node,
                    state=NodeState.STALE,
                    queued_job_id=None,
                    generation=generation,
                ),
            )
        return {
            "frontier": frozenset(frontier),
            "closure": frozenset(closure),
            "generation": generation,
        }

    def _enqueue_recompute(
        self,
        closure: Iterable[str],
        *,
        project_id: str,
        principal: Principal,
        acl_epoch: int,
        generation: int,
    ) -> list[tuple[Job, dict[str, Any]]]:
        ordered = topological_order(self.adjacency(), closure)
        snapshot = self.authorization.permission_snapshot_id()
        jobs: list[tuple[Job, dict[str, Any]]] = []
        for index, node_id in enumerate(ordered):
            node = self._peek(node_id)
            _, fingerprint_digest = digest_payload(
                {
                    "node_id": node.id,
                    "generation": generation,
                    "input_hashes": list(node.record.input_hashes),
                    "content_hash": node.content_hash,
                }
            )
            payload = {
                "node_id": node.id,
                "project_id": project_id,
                "generation": generation,
                "estimated_cost": 0.0,
                "authorization": {"action": "propose"},
            }
            job = self.jobs.enqueue(
                RECOMPUTE_JOB_TYPE,
                payload,
                actor_id=principal.actor_id,
                project_id=project_id,
                idempotency_key=f"recompute_node:{node.id}:{generation}",
                priority=100 - min(index, 99),
                cost_budget=1.0,
                timeout_seconds=60,
                max_attempts=3,
                input_fingerprint=fingerprint_digest,
                acl_epoch=acl_epoch,
                permission_snapshot_id=snapshot,
                trace_id=f"trc_{new_ulid()}",
            )
            jobs.append((job, payload))
        return jobs

    def _require(
        self,
        principal: Principal,
        action: Action,
        project_id: str,
        acl_epoch: int,
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
            context=AuthContext(snapshot_id=self.authorization.permission_snapshot_id()),
        )

    def _peek(self, node_id: str) -> StoredNode:
        return self._node(node_id, load_index(self.workspace))

    def _node(self, node_id: str, index: dict[str, Any]) -> StoredNode:
        digest = index["node_digests"].get(node_id)
        if digest is None:
            raise NodeNotFoundError(f"unknown dependency node: {node_id}")
        return StoredNode.from_dict(load_payload(self.workspace, str(digest)))

    def _put_node(self, index: dict[str, Any], node: StoredNode) -> None:
        digest = put_payload(self.workspace, node.to_dict())
        if node.id not in index["node_ids"]:
            index["node_ids"] = [*index["node_ids"], node.id]
        index["node_digests"][node.id] = digest
        project_nodes = list(index["project_nodes"].get(node.project_id, []))
        if node.id not in project_nodes:
            project_nodes.append(node.id)
        index["project_nodes"][node.project_id] = project_nodes
        if node.subject_id:
            index["subject_index"][node.subject_id] = node.id
        if node.queued_job_id:
            index["queued"][node.id] = node.queued_job_id
        else:
            index["queued"].pop(node.id, None)

    def _put_edge(self, index: dict[str, Any], edge: DependencyEdge) -> None:
        digest = put_payload(self.workspace, edge.to_dict())
        if edge.id not in index["edge_ids"]:
            index["edge_ids"] = [*index["edge_ids"], edge.id]
        index["edge_digests"][edge.id] = digest
        outgoing = list(index["outgoing"].get(edge.from_id, []))
        if edge.to_id not in outgoing:
            outgoing.append(edge.to_id)
        index["outgoing"][edge.from_id] = outgoing
        incoming = list(index["incoming"].get(edge.to_id, []))
        if edge.from_id not in incoming:
            incoming.append(edge.from_id)
        index["incoming"][edge.to_id] = incoming

    def _find_edge(
        self, index: dict[str, Any], from_id: str, to_id: str
    ) -> DependencyEdge | None:
        for edge_id in index["edge_ids"]:
            edge = DependencyEdge.from_dict(
                load_payload(self.workspace, str(index["edge_digests"][str(edge_id)]))
            )
            if edge.from_id == from_id and edge.to_id == to_id:
                return edge
        return None

    @staticmethod
    def _export_payload(view: NodeView, *, override: bool) -> dict[str, Any]:
        payload = view.to_dict()
        payload["override"] = override
        payload["consequential_export"] = True
        if view.state is NodeState.STALE:
            payload["current"] = False
            payload["labeled_stale"] = True
            payload["state"] = NodeState.STALE.value
        return payload


GraphService = DependencyEngine
