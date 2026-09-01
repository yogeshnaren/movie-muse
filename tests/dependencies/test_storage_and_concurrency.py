"""Blob-backed graph storage, crash/reopen, and serialized concurrent writes."""

from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.dependencies.api import INDEX_META_KEY, DependencyEngine, NodeKind, NodeState
from movie_muse.identity.api import IdentityService
from movie_muse.jobs.api import JobService
from movie_muse.persistence.api import LocalWorkspace


def _helpers():
    name = "movie_muse_mm011_helpers"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    path = Path(__file__).with_name("helpers.py")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_helpers_mod = _helpers()
MutableClock = _helpers_mod.MutableClock
boot_dependency_stack = _helpers_mod.boot_dependency_stack


def _table_names(workspace: LocalWorkspace) -> set[str]:
    rows = workspace.store.fetchall("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    return {str(row["name"]) for row in rows}


def test_dependencies_use_workspace_meta_without_new_tables(dep_stack) -> None:
    before = _table_names(dep_stack.workspace)
    dep_stack.add_source()
    after = _table_names(dep_stack.workspace)
    assert after == before
    digest = dep_stack.workspace.store.get_meta(INDEX_META_KEY)
    assert digest is not None
    assert dep_stack.workspace.store.blobs.exists(digest)
    assert "dependencies" not in after
    assert "dependency_nodes" not in after
    assert "dependency_edges" not in after


def test_airplane_mode_graph_and_invalidation_stay_local(dep_stack) -> None:
    dep_stack.workspace.set_airplane_mode(True)
    source = dep_stack.add_source()
    derived = dep_stack.add_derived([source.id])
    result = dep_stack.engine.invalidate_inputs(
        [source.id], principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert derived.id in result.closure
    view = dep_stack.engine.view_node(
        derived.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert view.state is NodeState.STALE


def test_crash_reopen_reloads_graph_from_blobs(tmp_path) -> None:
    stack = boot_dependency_stack(tmp_path / "ws")
    source = stack.add_source(subject_id="rev-keep")
    derived = stack.add_derived([source.id])
    stack.engine.invalidate_inputs(
        [source.id], principal=stack.principal, acl_epoch=stack.epoch
    )
    root = stack.workspace.root
    source_id, derived_id, project_id, owner_id = source.id, derived.id, stack.project.id, stack.owner.id
    stack.workspace.close()

    workspace = LocalWorkspace(root)
    identity = IdentityService(workspace)
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    clock = MutableClock()
    jobs = JobService(
        workspace,
        identity,
        authorization,
        audit,
        lambda job: job.input_fingerprint,
        clock=clock,
    )
    engine = DependencyEngine(workspace, authorization, jobs, audit)
    principal = identity.principal(owner_id)
    epoch = identity.acl_epoch()
    reloaded = engine.view_node(derived_id, principal=principal, acl_epoch=epoch)
    source_view = engine.view_node(source_id, principal=principal, acl_epoch=epoch)
    assert reloaded.state is NodeState.STALE
    assert reloaded.current is False
    assert reloaded.labeled_stale is True
    assert source_view.state is NodeState.CURRENT
    listed = engine.list_nodes(project_id, principal=principal, acl_epoch=epoch)
    assert {item.id for item in listed} == {source_id, derived_id}
    workspace.close()


def test_concurrent_add_edge_is_serialized(tmp_path) -> None:
    stack = boot_dependency_stack(tmp_path / "ws")
    left = stack.add_source()
    right = stack.add_source(kind=NodeKind.CONFIGURATION)
    join = stack.add_source(kind=NodeKind.MODEL)
    root = stack.workspace.root
    owner = stack.owner
    stack.workspace.close()

    barrier = threading.Barrier(2)
    created: list[str | None] = [None, None]
    errors: list[BaseException | None] = [None, None]

    def worker(index: int, from_id: str) -> None:
        workspace = None
        try:
            workspace = LocalWorkspace(root)
            identity = IdentityService(workspace)
            audit = AuditLog(workspace)
            authorization = AuthorizationService(workspace, identity, audit=audit)
            jobs = JobService(
                workspace,
                identity,
                authorization,
                audit,
                lambda job: job.input_fingerprint,
                clock=MutableClock(),
            )
            engine = DependencyEngine(workspace, authorization, jobs, audit)
            principal = identity.principal(owner.id)
            barrier.wait(timeout=5)
            edge = engine.add_edge(
                from_id=from_id,
                to_id=join.id,
                principal=principal,
                acl_epoch=identity.acl_epoch(),
            )
            created[index] = edge.id
        except Exception as exc:
            errors[index] = exc
        finally:
            if workspace is not None:
                workspace.close()

    threads = [
        threading.Thread(target=worker, args=(0, left.id)),
        threading.Thread(target=worker, args=(1, right.id)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert errors == [None, None]
    assert created[0] and created[1] and created[0] != created[1]
    workspace = LocalWorkspace(root)
    identity = IdentityService(workspace)
    engine = DependencyEngine(
        workspace,
        AuthorizationService(workspace, identity),
        JobService(
            workspace,
            identity,
            AuthorizationService(workspace, identity),
            AuditLog(workspace),
            lambda job: job.input_fingerprint,
            clock=MutableClock(),
        ),
    )
    principal = identity.principal(owner.id)
    adj = engine.adjacency()
    assert join.id in adj.get(left.id, ())
    assert join.id in adj.get(right.id, ())
    view = engine.view_node(join.id, principal=principal, acl_epoch=identity.acl_epoch())
    assert left.id in view.input_ids
    assert right.id in view.input_ids
    workspace.close()
