"""Builders for commercial forecast tests. Duplicated rather than imported."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from movie_muse.audience_lab.api import AudienceLabService
from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.breakdown.api import BreakdownService
from movie_muse.budget.api import BudgetService
from movie_muse.commercial_forecast.api import AssumptionKey, CommercialForecastService
from movie_muse.compiler.api import CompilerService
from movie_muse.creative_intent.api import CreativeIntentService
from movie_muse.dependencies.api import DependencyEngine
from movie_muse.identity.api import (
    Actor,
    IdentityService,
    Organization,
    PrincipalKind,
    Role,
    make_human_actor,
)
from movie_muse.jobs.api import JobService
from movie_muse.model_router.api import ModelRouter
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.proposals.api import ProposalService
from movie_muse.revisions.api import RevisionService
from movie_muse.rights.api import RightsService
from movie_muse.scheduling.api import ScheduleService
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    Project,
    ScreenplayDocument,
    Sequence,
    new_id,
)


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 19, 5, 0, tzinfo=UTC)

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
        title="Forecast Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_ids = (new_id("scene"), new_id("scene"), new_id("scene"))
    pair = new_id("dialogue_pair")
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Forecast Pilot",
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
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="Ada hangs her coat. A child watches from the doorway.",
                scene_id=scene_ids[0],
            ),
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
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="Ada takes a stunt fall from the fire escape.",
                scene_id=scene_ids[1],
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="INT. OFFICE - DAY",
                scene_id=scene_ids[2],
                scene_number="3",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="Ada files the call sheet.",
                scene_id=scene_ids[2],
            ),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


@dataclass
class ForecastStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    breakdown: BreakdownService
    schedule: ScheduleService
    budget: BudgetService
    lab: AudienceLabService
    forecast: CommercialForecastService
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


def boot_forecast_stack(root: Path) -> ForecastStack:
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
            name="Forecast Studio",
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
    router = ModelRouter(workspace, authorization, identity, audit)
    rights = RightsService(workspace, authorization, audit)
    intents = CreativeIntentService(workspace, authorization, revisions)
    lab = AudienceLabService(
        workspace, authorization, identity, audit, router, rights, revisions, intents
    )
    forecast = CommercialForecastService(
        workspace, authorization, identity, audit, budget, lab, clock=clock.stamp
    )
    return ForecastStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        breakdown=breakdown,
        schedule=schedule,
        budget=budget,
        lab=lab,
        forecast=forecast,
        project=project,
        owner=owner,
        clock=clock,
    )


def compile_budget(stack: ForecastStack):
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
    compiled = stack.schedule.compile(
        derived.projection.id,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        seed=1,
    )
    return stack.budget.compile(
        compiled.id,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )


def set_core_assumptions(stack: ForecastStack, *, as_of: str = "2024-12-31") -> None:
    values = {
        AssumptionKey.DISTRIBUTION: "limited theatrical plus SVOD window",
        AssumptionKey.MARKETING: "festival-to-specialty spend",
        AssumptionKey.RELEASE: "platform exclusive after 45-day theatrical",
        AssumptionKey.TERRITORY: "US",
        AssumptionKey.TALENT: "ensemble without a global star quote",
        AssumptionKey.PLATFORM: "specialty-svod",
    }
    for key, value in values.items():
        stack.forecast.set_assumption(
            stack.project.id,
            principal=stack.principal,
            acl_epoch=stack.epoch,
            key=key,
            value=value,
            data_as_of=as_of,
            evidence=f"producer memo {key.value}",
        )


def add_comparable(
    stack: ForecastStack,
    *,
    title: str,
    budget: float,
    observed_gross: float,
    release_date: str,
    data_as_of: str,
    territory: str = "US",
    platform: str = "specialty-svod",
):
    return stack.forecast.register_comparable(
        stack.project.id,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        title=title,
        territory=territory,
        platform=platform,
        budget=budget,
        observed_gross=observed_gross,
        release_date=release_date,
        data_as_of=data_as_of,
        source="internal released-outcome ledger",
        rationale=f"{title} matches specialty US SVOD because of budget class and release pattern.",
    )


def seed_in_distribution(stack: ForecastStack) -> None:
    add_comparable(
        stack,
        title="Latch Key",
        budget=800_000,
        observed_gross=2_400_000,
        release_date="2022-03-01",
        data_as_of="2022-12-31",
    )
    add_comparable(
        stack,
        title="Harbor Night",
        budget=1_100_000,
        observed_gross=3_000_000,
        release_date="2023-04-15",
        data_as_of="2023-12-31",
    )
    add_comparable(
        stack,
        title="Kitchen Watch",
        budget=950_000,
        observed_gross=2_200_000,
        release_date="2023-09-01",
        data_as_of="2024-01-15",
    )


def invite_role(stack: ForecastStack, role: Role):
    actor = make_human_actor(organization_id=stack.project.organization_id, display_name=role.value)
    stack.identity.register_actor(actor)
    invitation = stack.identity.invite(
        inviter_actor_id=stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=stack.project.id,
        role=role,
    )
    stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    return stack.identity.principal(actor.id)


@pytest.fixture
def forecast_stack(tmp_path: Path) -> ForecastStack:
    return boot_forecast_stack(tmp_path / "ws")


@pytest.fixture
def compiled_budget(forecast_stack: ForecastStack):
    return compile_budget(forecast_stack)


@pytest.fixture
def ready_forecast(forecast_stack: ForecastStack, compiled_budget):
    set_core_assumptions(forecast_stack)
    seed_in_distribution(forecast_stack)
    return compiled_budget


@pytest.fixture
def member(forecast_stack: ForecastStack):
    def _member(role: Role):
        return invite_role(forecast_stack, role)

    return _member
