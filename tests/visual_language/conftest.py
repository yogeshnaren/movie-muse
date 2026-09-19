"""Builders for visual-language tests. Duplicated rather than imported."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.director.api import DirectorVisionService, SubjectPosition
from movie_muse.identity.api import (
    Actor,
    IdentityService,
    Organization,
    PrincipalKind,
    Role,
    make_human_actor,
    make_integration_actor,
)
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.rights.api import PermittedUse, RightsService, SourceClassification
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    CameraSpec,
    Project,
    ScreenplayDocument,
    Sequence,
    new_id,
    new_ulid,
)
from movie_muse.shot_ir.api import ShotIRService
from movie_muse.visual_language.api import (
    EvolutionStep,
    LanguageRule,
    PaletteSwatch,
    RuleKind,
    SafetyReview,
    VisualLanguageService,
)


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 9, 19, 2, 20, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.value

    def stamp(self) -> str:
        return self.value.strftime("%Y-%m-%dT%H:%M:%SZ")

    def advance(self, seconds: int) -> str:
        self.value += timedelta(seconds=seconds)
        return self.stamp()


def make_document() -> tuple[Project, ScreenplayDocument, str, tuple[str, str]]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Visual Language Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_ids = (new_id("scene"), new_id("scene"))
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Visual Language Pilot",
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
                text="Ada writes a note in tungsten light.",
                scene_id=scene_ids[0],
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.SCENE_HEADING,
                text="EXT. HARBOR - NIGHT",
                scene_id=scene_ids[1],
                scene_number="2",
            ),
            Block(
                id=new_id("block"),
                kind=BlockKind.ACTION,
                text="A ferry horn sounds.",
                scene_id=scene_ids[1],
            ),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch"), scene_ids


@dataclass
class VisualStack:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    rights: RightsService
    director: DirectorVisionService
    shots: ShotIRService
    visual: VisualLanguageService
    project: Project
    document: ScreenplayDocument
    owner: Actor
    branch_id: str
    scene_ids: tuple[str, str]
    clock: MutableClock

    @property
    def principal(self):
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()


def boot_visual_stack(root: Path) -> VisualStack:
    project, document, branch_id, scene_ids = make_document()
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
            name="Palette Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    clock = MutableClock()
    rights = RightsService(workspace, authorization, audit)
    director = DirectorVisionService(
        workspace, authorization, audit, clock=clock.stamp
    )
    shots = ShotIRService(workspace, authorization, audit, director, clock=clock.stamp)
    visual = VisualLanguageService(
        workspace, authorization, audit, rights, shots, clock=clock.stamp
    )
    return VisualStack(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        rights=rights,
        director=director,
        shots=shots,
        visual=visual,
        project=project,
        document=document,
        owner=owner,
        branch_id=branch_id,
        scene_ids=scene_ids,
        clock=clock,
    )


def default_camera() -> CameraSpec:
    return CameraSpec(
        position_x=0.0,
        position_y=4.0,
        height_m=1.6,
        orientation_degrees=180.0,
        sensor="super35",
        lens_mm=35.0,
        movement="static",
    )


def open_space(stack: VisualStack, scene_id: str | None = None):
    return stack.director.create_scene_space(
        project_id=stack.project.id,
        scene_id=scene_id or stack.scene_ids[0],
        geometry_description="Kitchen 8m x 5m, island center.",
        principal=stack.principal,
        acl_epoch=stack.epoch,
        subject_positions=(
            SubjectPosition(subject_id="ada", x=1.5, y=2.0, orientation_degrees=90.0),
        ),
    )


def create_shot(stack: VisualStack, *, color_intent: str = "unspecified"):
    space = open_space(stack)
    return stack.shots.create_shot(
        scene_space_id=space.space.id,
        camera=default_camera(),
        composition_notes="Ada mid-frame at the island.",
        light_direction="window-left",
        performance_intent="restrained, listening",
        principal=stack.principal,
        acl_epoch=stack.epoch,
        eyeline_subject_ids=("ada",),
        color_intent=color_intent,
        continuity_notes="Match day kitchen eyeline.",
        coverage_purpose="master",
    )


def register_cited_source(stack: VisualStack, *, title: str = "Licensed stills"):
    return stack.rights.register_source(
        project_id=stack.project.id,
        title=title,
        classification=SourceClassification.LICENSED,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        permitted_uses=(PermittedUse.RETRIEVAL, PermittedUse.CITATION),
        license_summary="licensed for citation",
        license_expiry="2099-01-01T00:00:00Z",
    )


def default_palette() -> tuple[PaletteSwatch, ...]:
    return (
        PaletteSwatch(hex_color="#C47A3A", name="tungsten-amber", role="key"),
        PaletteSwatch(hex_color="#1B2A4A", name="night-navy", role="fill"),
        PaletteSwatch(hex_color="#F4E1C1", name="skin-highlight", role="skin"),
    )


def default_rules() -> tuple[LanguageRule, ...]:
    return (
        LanguageRule(
            id=f"vru_{new_ulid()}",
            kind=RuleKind.RULE,
            dimension="temperature",
            text="Keep interiors tungsten-warm against navy fills.",
        ),
        LanguageRule(
            id=f"vru_{new_ulid()}",
            kind=RuleKind.EXCEPTION,
            dimension="saturation",
            text="Harbor night may lift saturation on practicals only.",
        ),
        LanguageRule(
            id=f"vru_{new_ulid()}",
            kind=RuleKind.ANTI_RULE,
            dimension="skin_tone_rendering",
            text="Do not crush skin highlights into the navy fill.",
        ),
    )


def default_evolution() -> tuple[EvolutionStep, ...]:
    return (
        EvolutionStep(
            id=f"ves_{new_ulid()}",
            at="2026-09-01T00:00:00Z",
            note="Pilot pass: amber key, navy fill, protected skin.",
        ),
    )


def default_safety(*, skin_tone_safe: bool = True, accessibility_ok: bool = True) -> SafetyReview:
    return SafetyReview(
        skin_tone_safe=skin_tone_safe,
        accessibility_ok=accessibility_ok,
        notes="Reviewed against reference stills.",
    )


def record_language(stack: VisualStack, *, source_ids: tuple[str, ...] | None = None, **overrides):
    kwargs = {
        "project_id": stack.project.id,
        "palette": default_palette(),
        "contrast": "medium-high",
        "saturation": "restrained",
        "temperature": "tungsten-warm",
        "source_motivation": "practicals and window-left daylight",
        "lighting_ratio": "3:1 key to fill",
        "production_design": "aged brass, cream plaster",
        "wardrobe": "amber wool against navy oilskins",
        "skin_tone_rendering": "protect highlight roll-off",
        "lens_render_interaction": "35mm super35 mild halation on practicals",
        "composition": "mid-frame subject, negative space right",
        "temporal_progression": "warm day interiors to cooler harbor night",
        "safety": default_safety(),
        "principal": stack.principal,
        "acl_epoch": stack.epoch,
        "rules": default_rules(),
        "evolution": default_evolution(),
        "reference_source_ids": source_ids
        if source_ids is not None
        else (register_cited_source(stack).source_id,),
    }
    kwargs.update(overrides)
    return stack.visual.record_language(**kwargs)


def invite_role(stack: VisualStack, role: Role, *, integration: bool = False):
    factory = make_integration_actor if integration else make_human_actor
    actor = factory(organization_id=stack.project.organization_id, display_name=role.value)
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
def visual_stack(tmp_path: Path) -> VisualStack:
    return boot_visual_stack(tmp_path / "ws")


@pytest.fixture
def make_safety():
    return default_safety


@pytest.fixture
def cited_source(visual_stack: VisualStack):
    return register_cited_source(visual_stack)


@pytest.fixture
def recorded_language(visual_stack: VisualStack):
    def _record(**overrides):
        return record_language(visual_stack, **overrides)

    return _record


@pytest.fixture
def make_shot(visual_stack: VisualStack):
    def _shot(*, color_intent: str = "unspecified"):
        return create_shot(visual_stack, color_intent=color_intent)

    return _shot


@pytest.fixture
def member(visual_stack: VisualStack):
    def _member(role: Role, *, integration: bool = False):
        return invite_role(visual_stack, role, integration=integration)

    return _member
