"""MM-008 jobs fixtures; duplicated here rather than imported from other tests."""

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


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> datetime:
        self.value += timedelta(seconds=seconds)
        return self.value


@dataclass
class JobStack:
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
            "job_type": "derive_projection",
            "payload": {
                "authorization": {"action": "propose"},
                "estimated_cost": 1.0,
            },
            "actor_id": self.owner.id,
            "project_id": self.project.id,
            "idempotency_key": f"idem-{new_ulid()}",
            "priority": 10,
            "cost_budget": 5.0,
            "timeout_seconds": 60,
            "max_attempts": 3,
            "input_fingerprint": self.fingerprints[self.project.id],
            "acl_epoch": self.identity.acl_epoch(),
            "permission_snapshot_id": self.identity.permission_snapshot_id(),
            "trace_id": f"trace-{new_ulid()}",
        }
        values.update(overrides)
        return self.jobs.enqueue(**values)


def make_project_and_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_jobs",
        title="Jobs Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Jobs Pilot",
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
                text="INT. WORKROOM - DAY",
                scene_id=scene_id,
                scene_number="1",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="The durable worker wakes.",
            ),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


def boot_job_stack(root: Path) -> JobStack:
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
            name="Jobs Studio",
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
    return JobStack(
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
def job_stack(tmp_path: Path) -> JobStack:
    stack = boot_job_stack(tmp_path / "workspace")
    yield stack
    stack.workspace.close()
