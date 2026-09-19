"""MM-008 worker fixtures; duplicated here rather than imported from other tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.identity.api import Actor, IdentityService, Organization, PrincipalKind
from movie_muse.jobs.api import Job, JobService
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    Project,
    ScreenplayDocument,
    Sequence,
    new_id,
    new_ulid,
)
from movie_muse.worker.api import WorkerRuntime


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 1, 13, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> datetime:
        self.value += timedelta(seconds=seconds)
        return self.value


@dataclass
class WorkerStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    jobs: JobService
    project: Project
    owner: Actor
    clock: MutableClock
    fingerprints: dict[str, str]

    def enqueue(self, **overrides: Any) -> Job:
        values: dict[str, Any] = {
            "job_type": "worker_projection",
            "payload": {
                "authorization": {"action": "propose"},
                "estimated_cost": 0.5,
            },
            "actor_id": self.owner.id,
            "project_id": self.project.id,
            "idempotency_key": f"idem-{new_ulid()}",
            "priority": 5,
            "cost_budget": 3.0,
            "timeout_seconds": 60,
            "max_attempts": 3,
            "input_fingerprint": self.fingerprints[self.project.id],
            "acl_epoch": self.identity.acl_epoch(),
            "permission_snapshot_id": self.identity.permission_snapshot_id(),
            "trace_id": f"trace-{new_ulid()}",
        }
        values.update(overrides)
        return self.jobs.enqueue(**values)

    def worker(self, worker_id: str, *, lease_seconds: int = 10) -> WorkerRuntime:
        return WorkerRuntime(self.jobs, worker_id=worker_id, lease_seconds=lease_seconds)

    def restart(self) -> None:
        root = self.workspace.root
        self.workspace.close()
        self.workspace = LocalWorkspace(root)
        self.identity = IdentityService(self.workspace)
        self.audit = AuditLog(self.workspace)
        self.authorization = AuthorizationService(
            self.workspace,
            self.identity,
            audit=self.audit,
        )
        self.jobs = JobService(
            self.workspace,
            self.identity,
            self.authorization,
            self.audit,
            lambda job: self.fingerprints[job.project_id],
            clock=self.clock,
        )


def make_project_and_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_worker",
        title="Worker Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Worker Pilot",
        sequences=(
            Sequence(
                id=new_id("sequence"),
                title="Act One",
                order=0,
                scene_ids=(scene_id,),
            ),
        ),
        blocks=(
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="EXT. BACKLOT - NIGHT",
                scene_id=scene_id,
                scene_number="1",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="A replacement worker takes the lease.",
            ),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


def boot_worker_stack(root: Path) -> WorkerStack:
    project, document, branch_id = make_project_and_document()
    workspace = LocalWorkspace(root)
    workspace.open_project(project, document, branch_id=branch_id)
    identity = IdentityService(workspace)
    owner = Actor(
        id=project.owner_actor_id,
        display_name="Owner",
        principal_kind=PrincipalKind.HUMAN,
        organization_id=project.organization_id,
        created_at="2026-09-01T00:00:00Z",
    )
    identity.bootstrap(
        organization=Organization(
            id=project.organization_id,
            name="Worker Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    clock = MutableClock()
    fingerprints = {project.id: "input-v1"}
    jobs = JobService(
        workspace,
        identity,
        authorization,
        audit,
        lambda job: fingerprints[job.project_id],
        clock=clock,
    )
    return WorkerStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        jobs=jobs,
        project=project,
        owner=owner,
        clock=clock,
        fingerprints=fingerprints,
    )


@pytest.fixture
def worker_stack(tmp_path: Path) -> WorkerStack:
    stack = boot_worker_stack(tmp_path / "workspace")
    yield stack
    stack.workspace.close()
