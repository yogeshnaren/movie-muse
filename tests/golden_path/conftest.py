"""Builders for golden-path tests. Duplicated rather than imported from other packages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from movie_muse.artifacts.api import ArtifactService
from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.beats.api import BeatService
from movie_muse.breakdown.api import BreakdownService
from movie_muse.budget.api import BudgetService
from movie_muse.collaboration.api import CollaborationService
from movie_muse.compiler.api import CompilerService
from movie_muse.continuity.api import ContinuityService
from movie_muse.correspondence.api import CorrespondenceService
from movie_muse.creative_intent.api import CreativeIntentService
from movie_muse.dependencies.api import DependencyEngine
from movie_muse.director.api import DirectorVisionService
from movie_muse.editor.api import EditorService
from movie_muse.fdx.api import FdxService
from movie_muse.film_ir.api import FilmIrService
from movie_muse.identity.api import (
    Actor,
    IdentityService,
    Organization,
    PrincipalKind,
    Role,
    make_human_actor,
)
from movie_muse.insurance_readiness.api import InsuranceReadinessService
from movie_muse.jobs.api import JobService
from movie_muse.layout.api import LayoutService
from movie_muse.meeting_capture.api import MeetingCaptureService
from movie_muse.model_router.api import ModelRouter
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.platforms.api import GOLDEN_ACTOR_ID, golden_project_and_document
from movie_muse.project_memory.api import ProjectMemoryService
from movie_muse.proposals.api import ProposalService
from movie_muse.reference_lens.api import ReferenceLensService
from movie_muse.retrieval.api import RetrievalService
from movie_muse.revisions.api import RevisionService
from movie_muse.rights.api import RightsService
from movie_muse.room_mode.api import RoomModeService
from movie_muse.scheduling.api import ScheduleService
from movie_muse.schemas.api import Project, ScreenplayDocument
from movie_muse.security.api import ControlPlane
from movie_muse.shot_ir.api import ShotIRService
from movie_muse.state_engine.api import StateEngine
from movie_muse.storyboard.api import StoryboardService
from movie_muse.video_previs.api import VideoPrevisService
from movie_muse.visual_language.api import VisualLanguageService
from movie_muse.writer_unblock.api import WriterUnblockService


def _job_clock() -> datetime:
    return datetime(2026, 9, 1, 16, 0, tzinfo=UTC)


@dataclass
class GoldenStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    editor: EditorService
    compiler: CompilerService
    layout: LayoutService
    fdx: FdxService
    jobs: JobService
    graph: DependencyEngine
    proposals: ProposalService
    router: ModelRouter
    film_ir: FilmIrService
    intents: CreativeIntentService
    rights: RightsService
    retrieval: RetrievalService
    lens: ReferenceLensService
    unblock: WriterUnblockService
    state: StateEngine
    continuity: ContinuityService
    collab: CollaborationService
    memory: ProjectMemoryService
    rooms: RoomModeService
    artifacts: ArtifactService
    meetings: MeetingCaptureService
    beats: BeatService
    director: DirectorVisionService
    shots: ShotIRService
    visual: VisualLanguageService
    storyboard: StoryboardService
    previs: VideoPrevisService
    breakdown: BreakdownService
    schedules: ScheduleService
    budgets: BudgetService
    insurance: InsuranceReadinessService
    correspondence: CorrespondenceService
    plane: ControlPlane
    project: Project
    document: ScreenplayDocument
    owner: Actor
    branch_id: str

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()

    @property
    def snapshot(self) -> str:
        return self.identity.permission_snapshot_id()

    @property
    def head(self) -> str:
        return self.revisions.canon_branch().head_revision_id

    @property
    def canon_branch_id(self) -> str:
        return self.revisions.canon_branch().id

    def action_id(self) -> str:
        return next(
            block.id
            for block in self.revisions.replay_head().blocks
            if block.kind.value == "action"
        )

    def dialogue_id(self) -> str:
        return next(
            block.id
            for block in self.revisions.replay_head().blocks
            if block.kind.value == "dialogue"
        )

    def scene_id(self) -> str:
        heading = next(
            block
            for block in self.revisions.replay_head().blocks
            if block.kind.value == "scene_heading"
        )
        assert heading.scene_id is not None
        return heading.scene_id


def boot_golden_stack(root: Path) -> GoldenStack:
    project, document, branch_id = golden_project_and_document()
    workspace = LocalWorkspace(root)
    workspace.open_project(project, document, branch_id=branch_id)
    identity = IdentityService(workspace)
    owner = Actor(
        id=GOLDEN_ACTOR_ID,
        display_name="Golden Path Owner",
        principal_kind=PrincipalKind.HUMAN,
        organization_id=project.organization_id,
        created_at=project.created_at,
    )
    identity.bootstrap(
        organization=Organization(
            id=project.organization_id,
            name="Golden Path Studio",
            created_at=project.created_at,
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=owner.id)
    editor = EditorService(revisions, actor_id=owner.id)
    compiler = CompilerService()
    layout = LayoutService()
    fdx = FdxService()
    jobs = JobService(
        workspace,
        identity,
        authorization,
        audit,
        lambda job: job.input_fingerprint,
        clock=_job_clock,
    )
    graph = DependencyEngine(workspace, authorization, jobs, audit)
    proposals = ProposalService(revisions, authorization, audit, graph)
    router = ModelRouter(workspace, authorization, identity, audit)
    film_ir = FilmIrService(workspace, compiler, authorization, router)
    intents = CreativeIntentService(workspace, authorization, revisions)
    rights = RightsService(workspace, authorization, audit)
    retrieval = RetrievalService(workspace, rights, authorization, audit)
    lens = ReferenceLensService(retrieval, rights, authorization, audit)
    unblock = WriterUnblockService(
        proposals, revisions, authorization, audit, router, creative_intent=intents
    )
    state = StateEngine(workspace, authorization)
    continuity = ContinuityService(state, authorization, audit)
    collab = CollaborationService(revisions, authorization, audit)
    memory = ProjectMemoryService(workspace, authorization, audit)
    rooms = RoomModeService(memory, authorization, audit)
    artifacts = ArtifactService(workspace, authorization, revisions, audit)
    meetings = MeetingCaptureService(artifacts, memory, authorization, audit)
    beats = BeatService(workspace, authorization, audit, rights=rights, dependencies=graph)
    director = DirectorVisionService(workspace, authorization, audit, dependencies=graph)
    shots = ShotIRService(
        workspace, authorization, audit, director, dependencies=graph
    )
    visual = VisualLanguageService(workspace, authorization, audit, rights, shots)
    storyboard = StoryboardService(
        workspace,
        authorization,
        identity,
        audit,
        shots,
        director,
        artifacts,
        router,
        revisions,
    )
    previs = VideoPrevisService(
        workspace,
        authorization,
        identity,
        audit,
        shots,
        storyboard,
        artifacts,
        router,
        revisions,
        jobs,
    )
    breakdown = BreakdownService(
        workspace,
        authorization,
        audit,
        revisions,
        compiler=compiler,
        proposals=proposals,
        dependencies=graph,
    )
    schedules = ScheduleService(
        workspace,
        authorization,
        audit,
        revisions,
        breakdown,
        compiler=compiler,
        dependencies=graph,
    )
    budgets = BudgetService(workspace, authorization, audit, schedules, dependencies=graph)
    insurance = InsuranceReadinessService(
        workspace,
        authorization,
        audit,
        artifacts,
        budgets,
        schedules,
        breakdown,
        dependencies=graph,
        live_partner_configured=False,
    )
    correspondence = CorrespondenceService(
        workspace,
        authorization,
        audit,
        artifacts,
        revisions,
        live_channel_configured=False,
    )
    plane = ControlPlane(
        workspace,
        organization_id=project.organization_id,
        project_id=project.id,
    )
    return GoldenStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        editor=editor,
        compiler=compiler,
        layout=layout,
        fdx=fdx,
        jobs=jobs,
        graph=graph,
        proposals=proposals,
        router=router,
        film_ir=film_ir,
        intents=intents,
        rights=rights,
        retrieval=retrieval,
        lens=lens,
        unblock=unblock,
        state=state,
        continuity=continuity,
        collab=collab,
        memory=memory,
        rooms=rooms,
        artifacts=artifacts,
        meetings=meetings,
        beats=beats,
        director=director,
        shots=shots,
        visual=visual,
        storyboard=storyboard,
        previs=previs,
        breakdown=breakdown,
        schedules=schedules,
        budgets=budgets,
        insurance=insurance,
        correspondence=correspondence,
        plane=plane,
        project=project,
        document=document,
        owner=owner,
        branch_id=revisions.canon_branch().id,
    )


def invite_human(stack: GoldenStack, role: Role, display_name: str):
    actor = make_human_actor(
        organization_id=stack.project.organization_id, display_name=display_name
    )
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
def golden_stack(tmp_path: Path) -> GoldenStack:
    return boot_golden_stack(tmp_path / "golden-ws")
