"""Recompute jobs enqueue through JobService; hosts import dependencies.api only."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.authorization.api import Action, AuthorizationError
from movie_muse.dependencies.api import RECOMPUTE_JOB_TYPE, NodeState
from movie_muse.identity.api import Role, make_human_actor
from movie_muse.jobs.api import JobStatus
from movie_muse.toolchain.boundaries import scan_file
from movie_muse.toolchain.paths import repo_root


@pytest.mark.architecture
def test_host_importing_dependencies_api_is_allowed(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "dependency_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.dependencies.api import DependencyEngine\n", encoding="utf-8"
    )
    assert scan_file(tmp_path, source) == []


@pytest.mark.architecture
def test_host_importing_dependencies_internal_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "backend" / "app" / "dependency_routes.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from movie_muse.dependencies.service import DependencyEngine\n", encoding="utf-8"
    )
    violations = scan_file(tmp_path, source)
    assert len(violations) == 1
    assert violations[0].reason == "cross-module internal import"


@pytest.mark.architecture
def test_dependencies_package_imports_only_public_sibling_apis() -> None:
    package = repo_root() / "src" / "movie_muse" / "dependencies"
    siblings = (
        "audit",
        "authorization",
        "identity",
        "persistence",
        "schemas",
        "revisions",
        "jobs",
        "artifacts",
        "rights",
    )
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        for sibling in siblings:
            private_prefix = f"from movie_muse.{sibling}."
            public_import = f"from movie_muse.{sibling}.api import"
            assert private_prefix not in text.replace(public_import, "")


def test_invalidate_enqueues_recompute_jobs_visible_to_job_service(dep_stack) -> None:
    source = dep_stack.add_source()
    derived = dep_stack.add_derived([source.id])
    result = dep_stack.engine.invalidate_inputs(
        [source.id], principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert derived.id in result.closure
    assert result.jobs
    job = result.jobs[0]
    loaded = dep_stack.jobs.get(job.id)
    assert loaded.job_type == RECOMPUTE_JOB_TYPE
    assert loaded.status is JobStatus.QUEUED
    assert loaded.acl_epoch == dep_stack.epoch
    assert loaded.permission_snapshot_id == dep_stack.identity.permission_snapshot_id()
    payload = dep_stack.jobs.payload(job.id)
    assert payload["node_id"] == derived.id
    assert payload["authorization"]["action"] == "propose"
    leased = dep_stack.jobs.lease("worker-recompute", now=dep_stack.clock(), lease_seconds=20)
    assert leased is not None
    assert leased.id == job.id
    view = dep_stack.engine.view_node(
        derived.id, principal=dep_stack.principal, acl_epoch=dep_stack.epoch
    )
    assert view.state is NodeState.STALE
    assert view.queued_job_id == job.id


def test_viewer_cannot_mutate_graph(dep_stack) -> None:
    actor = make_human_actor(
        display_name="Viewer",
        organization_id=dep_stack.project.organization_id,
    )
    dep_stack.identity.register_actor(actor)
    invitation = dep_stack.identity.invite(
        inviter_actor_id=dep_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=dep_stack.project.id,
        role=Role.VIEWER,
    )
    dep_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    viewer = dep_stack.identity.principal(actor.id)
    with pytest.raises(AuthorizationError):
        dep_stack.engine.add_node(
            project_id=dep_stack.project.id,
            kind="source_revision",
            principal=viewer,
            acl_epoch=dep_stack.epoch,
        )
    source = dep_stack.add_source()
    view = dep_stack.engine.view_node(
        source.id, principal=viewer, acl_epoch=dep_stack.epoch
    )
    assert view.current is True
    decision = dep_stack.authorization.authorize(
        viewer,
        Action.PROPOSE,
        dep_stack.authorization.resource_for_project(dep_stack.project.id),
        acl_epoch=dep_stack.epoch,
    )
    assert decision.denied
