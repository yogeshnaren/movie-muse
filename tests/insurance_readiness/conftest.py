"""Builders for insurance-readiness tests. Duplicated rather than imported."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from movie_muse.artifacts.api import ArtifactService
from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.breakdown.api import BreakdownService
from movie_muse.budget.api import BudgetService
from movie_muse.compiler.api import CompilerService
from movie_muse.dependencies.api import DependencyEngine
from movie_muse.identity.api import Actor, IdentityService, Organization, PrincipalKind
from movie_muse.insurance_readiness.api import InsuranceReadinessService
from movie_muse.jobs.api import JobService
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.proposals.api import ProposalService
from movie_muse.revisions.api import RevisionService
from movie_muse.scheduling.api import ScheduleService
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    BudgetMaturity,
    Project,
    ScreenplayDocument,
    Sequence,
    new_id,
)


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 19, 1, 40, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def stamp(self) -> str:
        return self.value.strftime("%Y-%m-%dT%H:%M:%SZ")

    def advance(self, seconds: int) -> str:
        self.value += timedelta(seconds=seconds)
        return self.stamp()


def make_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Insurance Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_ids = (new_id("scene"), new_id("scene"), new_id("scene"))
    pair = new_id("dialogue_pair")
    kitchen = Block(
        id=new_id("block"),
        kind=BlockKind.ACTION,
        text="Ada hangs her coat. A child watches from the doorway.",
        scene_id=scene_ids[0],
    )
    alley = Block(
        id=new_id("block"),
        kind=BlockKind.ACTION,
        text="Ada takes a stunt fall from the fire escape.",
        scene_id=scene_ids[1],
    )
    office = Block(
        id=new_id("block"),
        kind=BlockKind.ACTION,
        text="Ada files the call sheet.",
        scene_id=scene_ids[2],
    )
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Insurance Pilot",
        sequences=(
            Sequence(
                id=new_id("sequence"),
                title="Act One",
                order=0,
                scene_ids=scene_ids,
            ),
        ),
        blocks=(
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="INT. KITCHEN - DAY",
                scene_id=scene_ids[0],
                scene_number="1",
            ),
            kitchen,
            Block(
                id=new_id("block"),
                kind=BlockKind.CHARACTER,
                text="ADA",
                character_cue_id=new_id("character_cue"),
                dialogue_pair_id=pair,
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.DIALOGUE,
                text="Keep the child back.",
                dialogue_pair_id=pair,
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="EXT. ALLEY - NIGHT",
                scene_id=scene_ids[1],
                scene_number="2",
            ),
            alley,
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="INT. OFFICE - DAY",
                scene_id=scene_ids[2],
                scene_number="3",
            ),
            office,
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


@dataclass
class InsuranceStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    artifacts: ArtifactService
    breakdown: BreakdownService
    schedule: ScheduleService
    budget: BudgetService
    insurance: InsuranceReadinessService
    project: Project
    owner: Actor
    clock: MutableClock

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()

    @property
    def head(self) -> str:
        return self.revisions.canon_head_id()


def boot_insurance_stack(root: Path, *, live_partner_configured: bool = False) -> InsuranceStack:
    project, document, branch_id = make_document()
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
            name="Insurance Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=owner.id)
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
    proposals = ProposalService(revisions, authorization, audit, graph=engine)
    artifacts = ArtifactService(workspace, authorization, revisions, audit)
    breakdown = BreakdownService(
        workspace,
        authorization,
        audit,
        revisions,
        compiler=CompilerService(),
        proposals=proposals,
        dependencies=engine,
        clock=clock.stamp,
    )
    schedule = ScheduleService(
        workspace,
        authorization,
        audit,
        revisions,
        breakdown,
        compiler=CompilerService(),
        dependencies=engine,
        clock=clock.stamp,
    )
    budget = BudgetService(
        workspace,
        authorization,
        audit,
        schedule,
        dependencies=engine,
        clock=clock.stamp,
    )
    insurance = InsuranceReadinessService(
        workspace,
        authorization,
        audit,
        artifacts,
        budget,
        schedule,
        breakdown,
        dependencies=engine,
        live_partner_configured=live_partner_configured,
        clock=clock.stamp,
    )
    return InsuranceStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        artifacts=artifacts,
        breakdown=breakdown,
        schedule=schedule,
        budget=budget,
        insurance=insurance,
        project=project,
        owner=owner,
        clock=clock,
    )


def compile_budget(stack: InsuranceStack):
    stack.breakdown.lock_source_revision(
        project_id=stack.project.id,
        revision_id=stack.head,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    derived = stack.breakdown.derive(
        project_id=stack.project.id,
        revision_id=stack.head,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    schedule = stack.schedule.compile(
        derived.projection.id,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        seed=1,
    )
    return stack.budget.compile(
        schedule.id,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        maturity=BudgetMaturity.PRELIMINARY_PRODUCTION_ESTIMATE,
    )


def compile_packet(stack: InsuranceStack):
    budget = compile_budget(stack)
    return stack.insurance.compile(
        budget.id,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )


@pytest.fixture
def insurance_stack(tmp_path: Path) -> InsuranceStack:
    return boot_insurance_stack(tmp_path / "ws")


@pytest.fixture
def compiled_budget(insurance_stack: InsuranceStack):
    return compile_budget(insurance_stack)


@pytest.fixture
def compiled_packet(insurance_stack: InsuranceStack):
    return compile_packet(insurance_stack)


@pytest.fixture
def live_insurance_stack(tmp_path: Path) -> InsuranceStack:
    return boot_insurance_stack(tmp_path / "live", live_partner_configured=True)


@pytest.fixture
def compiled_live_packet(live_insurance_stack: InsuranceStack):
    return compile_packet(live_insurance_stack)
