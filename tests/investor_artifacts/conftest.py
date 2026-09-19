"""Builders for investor-artifact tests. Duplicated rather than imported."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from movie_muse.artifacts.api import (
    ArtifactClassification,
    ArtifactService,
    ArtifactType,
)
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
from movie_muse.investor_artifacts.api import InvestorArtifactService, PackKind
from movie_muse.jobs.api import JobService
from movie_muse.model_router.api import ModelRouter
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.proposals.api import ProposalService
from movie_muse.revisions.api import RevisionService
from movie_muse.rights.api import PermittedUse, RightsService, SourceClassification
from movie_muse.scheduling.api import ScheduleService
from movie_muse.schemas.api import (
    ArtifactStatus,
    Block,
    BlockKind,
    Project,
    ScreenplayDocument,
    Sequence,
    new_id,
)

SOURCE_TEMPLATE_ID = "tmpl_reviewed_source"
SOURCE_TEMPLATE_VERSION = "1"
SOURCE_RENDERER_VERSION = "json/1"


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 19, 6, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def stamp(self) -> str:
        return self.value.strftime("%Y-%m-%dT%H:%M:%SZ")

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


def make_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Investor Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_ids = (new_id("scene"), new_id("scene"), new_id("scene"))
    pair = new_id("dialogue_pair")
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Investor Pilot",
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
class InvestorStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    artifacts: ArtifactService
    breakdown: BreakdownService
    schedule: ScheduleService
    budget: BudgetService
    rights: RightsService
    forecast: CommercialForecastService
    investor: InvestorArtifactService
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


def boot_investor_stack(root: Path) -> InvestorStack:
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
            name="Investor Studio",
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
    router = ModelRouter(workspace, authorization, identity, audit)
    rights = RightsService(workspace, authorization, audit)
    intents = CreativeIntentService(workspace, authorization, revisions)
    lab = AudienceLabService(
        workspace, authorization, identity, audit, router, rights, revisions, intents
    )
    forecast = CommercialForecastService(
        workspace, authorization, identity, audit, budget, lab, clock=clock.stamp
    )
    investor = InvestorArtifactService(
        workspace, authorization, audit, artifacts, budget, forecast, rights, clock=clock.stamp
    )
    principal = identity.principal(owner.id)
    epoch = identity.acl_epoch()
    artifacts.register_template(
        project_id=project.id,
        version=SOURCE_TEMPLATE_VERSION,
        renderer_version=SOURCE_RENDERER_VERSION,
        body="reviewed source {title}",
        principal=principal,
        acl_epoch=epoch,
        template_id=SOURCE_TEMPLATE_ID,
    )
    return InvestorStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        artifacts=artifacts,
        breakdown=breakdown,
        schedule=schedule,
        budget=budget,
        rights=rights,
        forecast=forecast,
        investor=investor,
        project=project,
        owner=owner,
        clock=clock,
    )


def compile_budget(stack: InvestorStack):
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


def set_core_assumptions(stack: InvestorStack, *, as_of: str = "2024-12-31") -> None:
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
    stack: InvestorStack,
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


def seed_in_distribution(stack: InvestorStack) -> None:
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


def invite_role(stack: InvestorStack, role: Role):
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


def register_citation_source(stack: InvestorStack, *, permitted_uses=None):
    uses = (PermittedUse.CITATION,) if permitted_uses is None else permitted_uses
    return stack.rights.register_source(
        project_id=stack.project.id,
        title="Producer citation ledger",
        classification=SourceClassification.LICENSED,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        permitted_uses=uses,
        license_summary="licensed for citation of reviewed artifacts",
        license_expiry="2099-01-01T00:00:00Z",
    )


def create_source_version(stack: InvestorStack, *, approved: bool = True) -> str:
    artifact = stack.artifacts.create_artifact(
        project_id=stack.project.id,
        artifact_type=ArtifactType.DOCUMENT,
        title="Reviewed lookbook",
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    view = stack.artifacts.create_version(
        artifact.id,
        inputs={"title": "Reviewed lookbook", "page_count": 1},
        source_revision_id=stack.head,
        template_id=SOURCE_TEMPLATE_ID,
        template_version=SOURCE_TEMPLATE_VERSION,
        renderer_version=SOURCE_RENDERER_VERSION,
        classification=ArtifactClassification.INTERNAL,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    if not approved:
        return view.version.id
    stack.artifacts.transition_review(
        view.version.id,
        ArtifactStatus.IN_REVIEW,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    approved_view = stack.artifacts.transition_review(
        view.version.id,
        ArtifactStatus.APPROVED,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    return approved_view.version.id


def compile_forecast(stack: InvestorStack, budget_id: str):
    set_core_assumptions(stack)
    seed_in_distribution(stack)
    return stack.forecast.forecast(
        stack.project.id,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        budget_id=budget_id,
        as_of="2024-12-31",
    )


def compile_pack(
    stack: InvestorStack,
    *,
    forecast_id: str,
    budget_id: str,
    source_version_ids,
    rights_source_id: str,
    kind: PackKind = PackKind.DECK,
):
    return stack.investor.compile(
        stack.project.id,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        kind=kind,
        budget_id=budget_id,
        forecast_id=forecast_id,
        source_version_ids=source_version_ids,
        rights_source_id=rights_source_id,
    )


@pytest.fixture
def investor_stack(tmp_path: Path) -> InvestorStack:
    return boot_investor_stack(tmp_path / "ws")


@pytest.fixture
def compiled_budget(investor_stack: InvestorStack):
    return compile_budget(investor_stack)


@pytest.fixture
def forecast_record(investor_stack: InvestorStack, compiled_budget):
    return compile_forecast(investor_stack, compiled_budget.id)


@pytest.fixture
def approved_source(investor_stack: InvestorStack) -> str:
    return create_source_version(investor_stack, approved=True)


@pytest.fixture
def citation_source(investor_stack: InvestorStack):
    return register_citation_source(investor_stack)


@pytest.fixture
def compiled_pack(
    investor_stack: InvestorStack,
    compiled_budget,
    forecast_record,
    approved_source: str,
    citation_source,
):
    return compile_pack(
        investor_stack,
        forecast_id=forecast_record.id,
        budget_id=compiled_budget.id,
        source_version_ids=(approved_source,),
        rights_source_id=citation_source.source_id,
    )


@pytest.fixture
def draft_source(investor_stack: InvestorStack) -> str:
    return create_source_version(investor_stack, approved=False)


@pytest.fixture
def retrieval_only_source(investor_stack: InvestorStack):
    return register_citation_source(
        investor_stack, permitted_uses=(PermittedUse.RETRIEVAL,)
    )


@pytest.fixture
def build_pack(
    investor_stack: InvestorStack,
    compiled_budget,
    forecast_record,
    approved_source: str,
    citation_source,
):
    def _build(
        *,
        kind: PackKind = PackKind.DECK,
        source_version_ids=None,
        rights_source_id: str | None = None,
        budget_id: str | None = None,
        forecast_id: str | None = None,
    ):
        return compile_pack(
            investor_stack,
            forecast_id=forecast_id or forecast_record.id,
            budget_id=budget_id or compiled_budget.id,
            source_version_ids=(
                (approved_source,) if source_version_ids is None else source_version_ids
            ),
            rights_source_id=(
                citation_source.source_id if rights_source_id is None else rights_source_id
            ),
            kind=kind,
        )

    return _build


@pytest.fixture
def member(investor_stack: InvestorStack):
    def _member(role: Role):
        return invite_role(investor_stack, role)

    return _member
