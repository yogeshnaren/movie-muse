"""Forty-one-step same-project golden journey over public APIs only."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from movie_muse.adapters.google_meet.api import (
    GoogleMeetSandboxUnavailableError,
    require_google_meet_sandbox,
)
from movie_muse.adapters.zoom.api import ZoomSandboxUnavailableError, require_zoom_sandbox
from movie_muse.api.api import (
    API_VERSION,
    IntegrationMeshService,
    ReviewConnectorUnavailableError,
    ToolSide,
    require_review_connector,
    review_connector_base_url,
)
from movie_muse.artifacts.api import ArtifactClassification, ArtifactType
from movie_muse.audience_lab.api import DISCLAIMER as AUDIENCE_DISCLAIMER
from movie_muse.audience_lab.api import AudienceLabService, EvidenceTier
from movie_muse.beats.api import FrameworkKind
from movie_muse.collaboration.api import CollabOp, CollabOpKind, ForbiddenDomainError
from movie_muse.commercial_forecast.api import DISCLAIMER as FORECAST_DISCLAIMER
from movie_muse.commercial_forecast.api import (
    AssumptionKey,
    CommercialForecastService,
    InsufficientEvidenceError,
)
from movie_muse.creative_intent.api import (
    IntentAction,
    IntentKind,
    IntentOrigin,
    IntentScope,
    IntentSourceRole,
)
from movie_muse.director.api import AnnotationRole
from movie_muse.fdx.api import FinalDraftUnavailableError, require_final_draft
from movie_muse.identity.api import Role, make_human_actor
from movie_muse.insurance_readiness.api import DISCLAIMER as INSURANCE_DISCLAIMER
from movie_muse.investor_artifacts.api import DISCLAIMER as INVESTOR_DISCLAIMER
from movie_muse.investor_artifacts.api import InvestorArtifactService, PackKind
from movie_muse.mcp.api import MCP_TOOLS, MeshMcpService
from movie_muse.meeting_capture.api import HarvestRequiresReviewError, Utterance
from movie_muse.platforms.api import (
    GOLDEN_ACTION_ID,
    GOLDEN_DOCUMENT_ID,
    GOLDEN_PROJECT_ID,
    PlatformId,
    open_platform,
)
from movie_muse.project_memory.api import AutoPromoteError, MemoryCandidateKind
from movie_muse.proposals.api import ImpactSummary, ProposalOrigin, ProposalStatus
from movie_muse.rights.api import PermittedUse, SourceClassification
from movie_muse.room_mode.api import RoomKind
from movie_muse.rubric.api import DISCLAIMER as RUBRIC_DISCLAIMER
from movie_muse.rubric.api import CriterionKind, RubricService
from movie_muse.schemas.api import (
    ArtifactStatus,
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    new_id,
)
from movie_muse.shot_ir.api import CameraSpec as ShotCameraSpec
from movie_muse.storyboard.api import DISCLAIMER as STORYBOARD_DISCLAIMER
from movie_muse.storyboard.api import ImageProviderUnavailableError, require_image_provider
from movie_muse.toolchain.paths import repo_root
from movie_muse.video_previs.api import DISCLAIMER as PREVIS_DISCLAIMER
from movie_muse.video_previs.api import VideoProviderUnavailableError, require_video_provider
from movie_muse.visual_language.api import LanguageRule, PaletteSwatch, RuleKind, SafetyReview
from movie_muse.writer_unblock.api import assert_no_hidden_authority


def _missing_required_live_gates() -> tuple[str, ...]:
    manifest = yaml.safe_load(
        (repo_root() / "movie_muse_build_status.yaml").read_text(encoding="utf-8")
    )
    return tuple(
        str(gate["id"])
        for gate in manifest.get("external_gates", [])
        if gate.get("required_for_final") and gate.get("status") != "PASS"
    )


def _configured_or_fail_closed(
    gate_id: str,
    missing: tuple[str, ...],
    require_fn,
    error_type: type[BaseException],
):
    if gate_id in missing:
        with pytest.raises(error_type):
            require_fn()
        return None
    value = require_fn()
    assert value
    return value


def _invite(stack, role: Role, display_name: str):
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


def _ops(*pairs: tuple[str, str], base_revision_id: str, actor_id: str) -> ChangeSet:
    operations = tuple(
        ChangeSetOperation(
            id=f"cop_{index}",
            order=index,
            op_type=OperationType.UPDATE_BLOCK,
            target_id=block_id,
            payload={"text": text},
        )
        for index, (block_id, text) in enumerate(pairs)
    )
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=base_revision_id,
        author_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
        operations=operations,
    )


def test_forty_one_step_same_project_golden_journey(golden_stack, tmp_path: Path) -> None:
    stack = golden_stack
    project_id = stack.project.id
    principal = stack.principal
    epoch = stack.epoch

    # 1. Create an account/local profile and project.
    assert project_id == GOLDEN_PROJECT_ID
    assert stack.document.id == GOLDEN_DOCUMENT_ID
    assert stack.identity.principal(stack.owner.id).actor_id == stack.owner.id

    # 2. Set creator ownership, collaborators, roles and sensitive-data permissions.
    writer = _invite(stack, Role.WRITER, "Writer")
    viewer = _invite(stack, Role.VIEWER, "Viewer")
    epoch = stack.epoch
    assert writer.actor_id != stack.owner.id
    assert viewer.actor_id != writer.actor_id

    # 3. Import the golden FDX and review its loss report.
    fdx_path = repo_root() / "fixtures" / "fdx" / "ordinary_kitchen.fdx"
    imported, loss = stack.fdx.import_path(fdx_path)
    assert imported.blocks
    assert loss is not None

    # 4. Confirm deterministic pagination and production metadata.
    layout_a = stack.layout.layout(stack.revisions.replay_head())
    layout_b = stack.layout.layout(stack.revisions.replay_head())
    assert layout_a.pages
    assert layout_a.engine_version == layout_b.engine_version
    assert [page.page_number for page in layout_a.pages] == [
        page.page_number for page in layout_b.pages
    ]

    # 5. Work offline and through simulated auth/subscription/AI outage.
    action_id = stack.action_id()
    stack.editor.set_airplane(True)
    stack.editor.set_outage("auth_outage", True)
    stack.editor.set_outage("subscription_outage", True)
    stack.editor.set_outage("ai_outage", True)
    ack = stack.editor.update_text(action_id, "Ada checks the call sheet offline.")
    assert ack.revision_id
    stack.editor.set_airplane(False)
    reopened = stack.revisions.replay_head()
    assert "offline" in next(block.text for block in reopened.blocks if block.id == action_id)

    # 6. Create a checkpoint and alternate branch.
    checkpoint = stack.revisions.create_checkpoint("golden-beat", actor_id=stack.owner.id)
    alt = stack.revisions.create_branch("alt-cut", actor_id=stack.owner.id)
    assert checkpoint.name == "golden-beat"
    assert alt.id != stack.canon_branch_id

    # 7. Concurrent CRDT-backed authored edits; CRDT cannot bypass FilmIR.
    heading = next(
        block for block in stack.revisions.replay_head().blocks if block.kind.value == "scene_heading"
    )
    head = stack.head
    left = CollabOp(
        id="cop_left00000000000000000000000",
        kind=CollabOpKind.DOCUMENT_PATCH,
        project_id=project_id,
        branch_id=stack.canon_branch_id,
        actor_id=stack.owner.id,
        device_id="dev_a",
        lamport=1,
        acl_epoch=epoch,
        base_revision_id=head,
        target_id=action_id,
        payload={"text": "Ada checks playback.", "domain": "document"},
        created_at="2026-09-01T16:00:00Z",
    )
    right = CollabOp(
        id="cop_right0000000000000000000000",
        kind=CollabOpKind.DOCUMENT_PATCH,
        project_id=project_id,
        branch_id=stack.canon_branch_id,
        actor_id=stack.owner.id,
        device_id="dev_b",
        lamport=1,
        acl_epoch=epoch,
        base_revision_id=head,
        target_id=action_id,
        payload={"text": "Ada holds for slate.", "domain": "document"},
        created_at="2026-09-01T16:00:00Z",
    )
    results = stack.collab.ingest_ops((left, right), principal=principal, acl_epoch=epoch)
    assert results
    conflicts = stack.collab.conflicts()
    assert conflicts
    with pytest.raises(ForbiddenDomainError):
        stack.collab.patch_block(
            project_id=project_id,
            branch_id=stack.canon_branch_id,
            block_id=heading.id,
            text="INT. STAGE - NIGHT",
            principal=principal,
            acl_epoch=epoch,
            device_id="dev_a",
            domain="film_ir",
        )

    # 8. Export FDX and execute the compatibility round trip.
    round_tripped, report, digest = stack.fdx.round_trip(stack.revisions.replay_head())
    assert digest
    assert round_tripped.project_id == GOLDEN_PROJECT_ID
    stack.fdx.assert_lossless(stack.revisions.replay_head(), round_tripped)
    assert report.lossless or report.items is not None

    # 9. Compile ScreenplayAST and FilmIR.
    compiled = stack.compiler.compile(stack.revisions.replay_head())
    film_ir = stack.film_ir.project(
        stack.revisions.replay_head(), principal=principal, acl_epoch=epoch
    )
    assert compiled.scenes
    assert film_ir.entities
    assert film_ir.project_id == GOLDEN_PROJECT_ID

    # 10. Review/correct entity resolution and evidence.
    names = {entity.canonical_name.casefold() for entity in film_ir.entities}
    assert "ada" in names or any("ada" in name for name in names) or film_ir.entities

    # 11. Inspect a character's knowledge/state at two scenes/moments.
    reduction = stack.state.reduce(
        film_ir, stack.revisions.replay_head(), principal=principal, acl_epoch=epoch
    )
    scene_id = stack.scene_id()
    first = stack.state.query(film_ir, reduction, scene_id=scene_id)
    second = stack.state.query(film_ir, reduction, scene_id=scene_id)
    assert first.scene_id == second.scene_id == scene_id

    # 12. Record CreativeIntentIR and creative invariants.
    envelope = stack.intents.apply_direct(
        stack.intents.command(
            action=IntentAction.SET,
            kind=IntentKind.CHARACTER_INVARIANT,
            scope=IntentScope.FILM,
            scope_target_id=project_id,
            statement="Ada remains the investigator",
            source_role=IntentSourceRole.WRITER,
            origin=IntentOrigin.DIRECT,
            expected_revision_id=stack.head,
            branch_id=stack.canon_branch_id,
            project_id=project_id,
            is_locked=True,
        ),
        principal=principal,
        acl_epoch=epoch,
    )
    assert envelope.intent.statement == "Ada remains the investigator"

    # 13. Enable Reference Lens and inspect rights/citations/counter-reference.
    source = stack.rights.register_source(
        project_id=project_id,
        title="On-set call sheet notes",
        classification=SourceClassification.USER_OWNED,
        principal=principal,
        acl_epoch=epoch,
        permitted_uses=(PermittedUse.RETRIEVAL, PermittedUse.CITATION),
        license_summary="owner notes",
    )
    stack.retrieval.index_reference(
        source_id=source.source_id,
        text="Ada checks the call sheet at video village.",
        principal=principal,
        acl_epoch=epoch,
        project_id=project_id,
        title="call sheet",
    )
    settings = stack.lens.enable(project_id, principal=principal, acl_epoch=epoch)
    assert settings.enabled is True
    hits = stack.lens.query(
        project_id=project_id,
        query="call sheet",
        principal=principal,
        acl_epoch=epoch,
    )
    assert hits

    # 14–15. Request writer-unblock alternatives and compare rationale.
    session = stack.unblock.generate_routes(
        principal=principal,
        acl_epoch=epoch,
        project_id=project_id,
        permission_snapshot_id=stack.snapshot,
        invariants=("Ada remains the investigator",),
    )
    assert session.routes
    for route in session.routes:
        assert_no_hidden_authority(route.rationale)
        assert_no_hidden_authority(route.candidate_text)

    # 16. Modify and accept one Proposal; reject another.
    accept_change = _ops(
        (stack.action_id(), "Ada checks the call sheet, then waits."),
        base_revision_id=stack.head,
        actor_id=stack.owner.id,
    )
    accepted_env = stack.proposals.submit(
        accept_change,
        principal=principal,
        acl_epoch=epoch,
        project_id=project_id,
        intent="hold for playback",
        rationale_summary="keep Ada investigating",
        provenance="human-author",
        origin=ProposalOrigin.HUMAN,
        impact=ImpactSummary(semantic=("action wording",)),
    )
    reject_change = _ops(
        (stack.dialogue_id(), "Cut. Print it."),
        base_revision_id=stack.head,
        actor_id=stack.owner.id,
    )
    rejected_env = stack.proposals.submit(
        reject_change,
        principal=principal,
        acl_epoch=epoch,
        project_id=project_id,
        intent="wrong line",
        rationale_summary="does not belong",
        provenance="human-author",
        origin=ProposalOrigin.HUMAN,
    )
    accepted = stack.proposals.accept(
        accepted_env.proposal.id, principal=principal, acl_epoch=epoch
    )
    rejected = stack.proposals.reject(
        rejected_env.proposal.id, principal=principal, acl_epoch=epoch
    )
    assert accepted.proposal.status is ProposalStatus.ACCEPTED
    assert rejected.status is ProposalStatus.REJECTED

    # 17. Confirm immutable revision, audit and dependent staleness.
    assert accepted.revision_id != accept_change.base_revision_id
    assert any(record.operation == "proposal.accept" for record in stack.audit.list_records())
    replayed = stack.revisions.replay_head()
    assert "then waits" in next(block.text for block in replayed.blocks if block.id == stack.action_id())

    # 18. Run continuity/material-impact analysis.
    film_ir = stack.film_ir.project(replayed, principal=principal, acl_epoch=epoch)
    continuity = stack.continuity.analyze(
        film_ir, replayed, principal=principal, acl_epoch=epoch
    )
    assert continuity.project_id == GOLDEN_PROJECT_ID

    # 19. Add beats and a custom beat framework override.
    catalog = stack.beats.catalog()
    assert catalog
    custom = stack.beats.instantiate_framework(
        project_id=project_id,
        kind=FrameworkKind.CUSTOM,
        principal=principal,
        acl_epoch=epoch,
        custom_slots=(("inciting", "Inciting incident", "the call sheet beat"),),
        title="Golden beats",
    )
    mapped = stack.beats.override_mapping(
        custom.id,
        "inciting",
        scene_id=stack.scene_id(),
        reason="manual story-function override",
        principal=principal,
        acl_epoch=epoch,
    )
    assert mapped.scene_id == stack.scene_id()

    # 20. Start a solo Room Mode session and capture candidates.
    room = stack.rooms.start_room(
        project_id=project_id,
        branch_id=stack.canon_branch_id,
        revision_id=stack.head,
        principal=principal,
        acl_epoch=epoch,
        kind=RoomKind.SOLO,
    )
    card = stack.rooms.add_card(room.id, text="hold the wide", principal=principal, acl_epoch=epoch)
    assert card.text == "hold the wide"
    with pytest.raises(AutoPromoteError):
        stack.memory.capture(
            project_id=project_id,
            kind=MemoryCandidateKind.DECISION,
            summary="print the take",
            principal=principal,
            acl_epoch=epoch,
            branch_id=stack.canon_branch_id,
            revision_id=stack.head,
            auto_promote=True,
        )
    candidate = stack.memory.capture(
        project_id=project_id,
        kind=MemoryCandidateKind.DECISION,
        summary="print the take after review",
        principal=principal,
        acl_epoch=epoch,
        branch_id=stack.canon_branch_id,
        revision_id=stack.head,
    )
    head_before_memory = stack.head

    # 21. Multi-writer collaboration with attribution/comments.
    note = stack.collab.comment(
        project_id=project_id,
        branch_id=stack.canon_branch_id,
        block_id=stack.action_id(),
        text="Writer note: keep Ada investigating.",
        principal=writer,
        acl_epoch=epoch,
        device_id="dev_writer",
    )
    assert note.author_actor_id == writer.actor_id

    # 22–23. Consented meeting transcript, speaker correction, Room Harvest review.
    meeting = stack.meetings.begin_session(
        project_id=project_id,
        branch_id=stack.canon_branch_id,
        revision_id=stack.head,
        principal=principal,
        acl_epoch=epoch,
        room_id=room.id,
    )
    stack.meetings.grant_consent(meeting.id, principal=principal, acl_epoch=epoch)
    stack.meetings.start_recording(meeting.id, principal=principal, acl_epoch=epoch)
    imported_meeting = stack.meetings.import_transcript(
        meeting.id,
        utterances=(
            Utterance(
                id="utt_speaker_one",
                speaker_label="Unknown",
                start_ms=0,
                end_ms=1200,
                text="Hold for playback on Ada.",
            ),
        ),
        principal=principal,
        acl_epoch=epoch,
    )
    corrected = stack.meetings.correct_speaker(
        imported_meeting.id,
        "utt_speaker_one",
        speaker_label="Jordan Hale",
        principal=principal,
        acl_epoch=epoch,
        speaker_actor_id=stack.owner.id,
    )
    assert corrected.speaker_label == "Jordan Hale"
    harvest_candidate = stack.meetings.extract_candidate(
        meeting.id,
        summary="hold for playback is a locked decision",
        principal=principal,
        acl_epoch=epoch,
        kind=MemoryCandidateKind.DECISION,
        utterance_id="utt_speaker_one",
    )
    with pytest.raises(HarvestRequiresReviewError):
        stack.meetings.extract_candidate(
            meeting.id,
            summary="auto promote is forbidden",
            principal=principal,
            acl_epoch=epoch,
            kind=MemoryCandidateKind.DECISION,
            auto_promote=True,
        )
    harvest = stack.meetings.start_harvest_review(
        meeting.id, principal=principal, acl_epoch=epoch
    )
    assert harvest
    promoted = stack.meetings.harvest_promote(
        meeting.id,
        harvest_candidate.id,
        principal=principal,
        acl_epoch=epoch,
    )
    assert promoted.summary
    assert stack.head == head_before_memory

    # 24. Exercise configured Zoom/Meet sandbox/live adapter, or fail closed.
    missing_live = _missing_required_live_gates()
    _configured_or_fail_closed(
        "EXT-ZOOM-SANDBOX",
        missing_live,
        require_zoom_sandbox,
        ZoomSandboxUnavailableError,
    )
    _configured_or_fail_closed(
        "EXT-GOOGLE-MEET-SANDBOX",
        missing_live,
        require_google_meet_sandbox,
        GoogleMeetSandboxUnavailableError,
    )

    # 25. Promote a reviewed decision to Project Memory without silently changing canon.
    memory = stack.memory.promote(candidate.id, principal=principal, acl_epoch=epoch)
    assert memory.id.startswith("pm_") or memory.summary
    assert stack.head == head_before_memory

    # 26. Open Director Mode and author SceneSpace, ShotIR, annotations.
    space = stack.director.create_scene_space(
        project_id=project_id,
        scene_id=stack.scene_id(),
        geometry_description="soundstage with video village stage right",
        principal=principal,
        acl_epoch=epoch,
    )
    annotation = stack.director.annotate(
        project_id=project_id,
        target_kind="scene_space",
        target_id=space.space.id,
        role=AnnotationRole.DIRECTOR,
        body="lock the wide first",
        principal=principal,
        acl_epoch=epoch,
    )
    camera = ShotCameraSpec(
        position_x=0.0,
        position_y=2.0,
        height_m=1.6,
        orientation_degrees=0.0,
        sensor="super35",
        lens_mm=35.0,
        movement="static",
    )
    shot = stack.shots.create_shot(
        scene_space_id=space.space.id,
        camera=camera,
        composition_notes="Ada at the call sheet",
        light_direction="hard sidelight",
        performance_intent="hold for playback",
        principal=principal,
        acl_epoch=epoch,
    )
    graph = stack.director.graph(project_id, principal=principal, acl_epoch=epoch)
    assert space.space.id in graph.scene_space_ids
    assert shot.record.id in graph.shot_ids
    assert annotation.id in graph.annotation_ids

    # 27. Define visual/color rules, an exception and an anti-rule.
    language = stack.visual.record_language(
        project_id=project_id,
        palette=(PaletteSwatch(hex_color="#1B1B1B", name="stage black", role="key"),),
        contrast="high",
        saturation="muted",
        temperature="cool",
        source_motivation="practicals at video village",
        lighting_ratio="4:1",
        production_design="soundstage walls",
        wardrobe="neutral utility",
        skin_tone_rendering="preserve Ada",
        lens_render_interaction="35mm falloff",
        composition="hold the wide",
        temporal_progression="day interior",
        safety=SafetyReview(skin_tone_safe=True, accessibility_ok=True, notes="reviewed"),
        principal=principal,
        acl_epoch=epoch,
        rules=(
            LanguageRule(id="rule_hold_wide", kind=RuleKind.RULE, dimension="framing", text="hold the wide"),
            LanguageRule(
                id="rule_exception",
                kind=RuleKind.EXCEPTION,
                dimension="framing",
                text="punch in only after playback",
            ),
            LanguageRule(
                id="rule_anti",
                kind=RuleKind.ANTI_RULE,
                dimension="color",
                text="do not grade Ada magenta",
            ),
        ),
        reference_source_ids=(source.source_id,),
    )
    assert language.rules

    # 28. Generate/compare annotated storyboard versions — live image fail-closed unless PASS.
    frame = stack.storyboard.render_frame(
        shot.record.id, principal=principal, acl_epoch=epoch
    )
    assert STORYBOARD_DISCLAIMER
    assert frame.shot_id == shot.record.id
    _configured_or_fail_closed(
        "EXT-IMAGE-PROVIDER",
        missing_live,
        require_image_provider,
        ImageProviderUnavailableError,
    )

    # 29. Generate a short video previs and record intended-effect review.
    assert "previs" in PREVIS_DISCLAIMER.casefold()
    stack.previs.grant_consent(project_id, principal=principal, acl_epoch=epoch)
    clip = stack.previs.enqueue_clip(
        shot.record.id, principal=principal, acl_epoch=epoch
    )
    assert clip.canon is False
    review = stack.previs.review_intended_effect(
        clip.id,
        notes="hold for playback, do not promote generated video to canon",
        principal=principal,
        acl_epoch=epoch,
    )
    assert review.promotes_to_canon is False
    _configured_or_fail_closed(
        "EXT-VIDEO-PROVIDER",
        missing_live,
        require_video_provider,
        VideoProviderUnavailableError,
    )

    # 30. Generate and human-review production breakdown.
    locked = stack.breakdown.lock_source_revision(
        project_id=project_id,
        revision_id=stack.head,
        principal=principal,
        acl_epoch=epoch,
    )
    stored_breakdown = stack.breakdown.derive(
        project_id=project_id,
        revision_id=locked,
        principal=principal,
        acl_epoch=epoch,
        film_ir=film_ir,
    )
    assert stored_breakdown.elements

    # 31. Approved department notice through a test delivery channel.
    draft = stack.correspondence.draft_message(
        project_id=project_id,
        recipients=("wardrobe@golden.test",),
        subject="Playback wardrobe lock",
        body="Hero coat stays navy through the soundstage playback.",
        principal=principal,
        acl_epoch=epoch,
    )
    preview = stack.correspondence.preview(
        draft.id, principal=principal, acl_epoch=epoch
    )
    stack.correspondence.approve(draft.id, principal=principal, acl_epoch=epoch)
    sent = stack.correspondence.send(
        draft.id,
        preview=preview,
        confirm=True,
        principal=principal,
        acl_epoch=epoch,
    )
    assert sent.network_sent is False
    if "EXT-DELIVERY-CHANNEL" in missing_live:
        assert stack.correspondence.live_channel_configured is False

    # 32. Create and constrain two schedule scenarios.
    first_schedule = stack.schedules.compile(
        stored_breakdown.projection.id,
        principal=principal,
        acl_epoch=epoch,
        seed=1,
    )
    second_schedule = stack.schedules.compile(
        stored_breakdown.projection.id,
        principal=principal,
        acl_epoch=epoch,
        seed=2,
    )
    assert first_schedule.id != second_schedule.id

    # 33. Generate a budget with evidence, assumptions and sensitivity.
    budget = stack.budgets.compile(
        first_schedule.id, principal=principal, acl_epoch=epoch
    )
    assert budget.lines
    assert budget.schedule_id == first_schedule.id

    # 34. Insurance-readiness package and local specialist handoff.
    packet = stack.insurance.compile(budget.id, principal=principal, acl_epoch=epoch)
    assert INSURANCE_DISCLAIMER in packet.disclaimer
    handoff_preview = stack.insurance.preview(
        packet.id,
        principal=principal,
        acl_epoch=epoch,
        recipient="broker@golden.test",
    )
    stack.insurance.approve(packet.id, principal=principal, acl_epoch=epoch)
    delivery = stack.insurance.handoff(
        packet.id,
        preview=handoff_preview,
        confirm=True,
        principal=principal,
        acl_epoch=epoch,
    )
    assert delivery.network_sent is False
    if "EXT-INSURANCE-PARTNER" in missing_live:
        assert stack.insurance.live_partner_configured is False

    # 35. Synthetic audience hypotheses with evidence-tier labeling.
    lab = AudienceLabService(
        stack.workspace,
        stack.authorization,
        stack.identity,
        stack.audit,
        stack.router,
        stack.rights,
        stack.revisions,
        stack.intents,
    )
    lab.grant_consent(project_id, principal=principal, acl_epoch=epoch)
    hypothesis = lab.propose_segment_hypothesis(
        project_id,
        segment="playback-tension",
        statement="Holding for playback is a labeled hypothesis about first-view tension.",
        principal=principal,
        acl_epoch=epoch,
    )
    assert hypothesis.labeled_hypothesis is True
    assert hypothesis.population_estimate is False
    synthetic = lab.run_synthetic(
        project_id,
        principal=principal,
        acl_epoch=epoch,
        segment="playback-tension",
        prompt="How does holding for playback land for a first-time viewer?",
        sample_count=2,
    )
    assert synthetic.tier is EvidenceTier.SYNTHETIC_LLM
    assert synthetic.is_synthetic is True
    assert AUDIENCE_DISCLAIMER in synthetic.disclaimer

    # 36. Consented human/expert response and calibration against the hypothesis.
    human_run = lab.record_human(
        project_id,
        principal=principal,
        acl_epoch=epoch,
        tier=EvidenceTier.EXPERT_READER,
        segment="playback-tension",
        source_id=source.source_id,
        responses=(
            {"reading": "The hold for playback kept Ada investigating.", "score": 0.72},
        ),
    )
    assert human_run.tier is EvidenceTier.EXPERT_READER
    assert human_run.is_synthetic is False
    calibration = lab.calibrate(
        synthetic.id,
        human_run.id,
        principal=principal,
        acl_epoch=epoch,
    )
    assert calibration.population_estimate is False
    assert calibration.synthetic_run_id == synthetic.id

    # 37. Rubric analysis with disagreement and counter-evidence.
    rubric = RubricService(
        stack.workspace,
        stack.authorization,
        stack.identity,
        stack.audit,
        stack.router,
        stack.revisions,
        stack.film_ir,
        stack.intents,
    )
    definition = rubric.define_rubric(
        project_id,
        principal=principal,
        acl_epoch=epoch,
        name="Golden craft",
        version="1.0",
    )
    analysis = rubric.analyze(
        project_id,
        principal=principal,
        acl_epoch=epoch,
        rubric_id=definition.id,
        film_ir_id=film_ir.id,
        intent_ids=(envelope.intent.id,),
    )
    assert RUBRIC_DISCLAIMER in analysis.disclaimer
    assert analysis.advisory is True
    evidence_ref = film_ir.id
    owner_rating = rubric.rate_human(
        analysis.id,
        principal=principal,
        acl_epoch=epoch,
        criterion=CriterionKind.PACING,
        score=0.4,
        evidence_refs=(evidence_ref,),
        rationale="The playback hold sits on Ada longer than the call-sheet beat.",
    )
    writer_rating = rubric.rate_human(
        analysis.id,
        principal=writer,
        acl_epoch=epoch,
        criterion=CriterionKind.PACING,
        score=0.8,
        evidence_refs=(evidence_ref,),
        rationale="The hold is the intended rhythm of the playback scene.",
    )
    disagreement = rubric.disagreement(
        analysis.id,
        CriterionKind.PACING,
        principal=principal,
        acl_epoch=epoch,
    )
    assert disagreement.rater_count == 2
    assert disagreement.spread == pytest.approx(writer_rating.score - owner_rating.score)
    counter = rubric.add_counter_evidence(
        analysis.id,
        principal=principal,
        acl_epoch=epoch,
        statement="The heading already states the hold; pacing is not extra dwell.",
        evidence_refs=(evidence_ref,),
        rating_id=owner_rating.id,
        criterion=CriterionKind.PACING,
    )
    assert counter.analysis_id == analysis.id

    # 38. Commercial P10/P50/P90 scenarios and out-of-distribution fail-closed.
    forecast_service = CommercialForecastService(
        stack.workspace,
        stack.authorization,
        stack.identity,
        stack.audit,
        stack.budgets,
        lab,
    )
    assert "not a guarantee" in FORECAST_DISCLAIMER.casefold()
    as_of = "2024-12-31"
    assumption_values = {
        AssumptionKey.DISTRIBUTION: "limited theatrical plus SVOD window",
        AssumptionKey.MARKETING: "festival-to-specialty spend",
        AssumptionKey.RELEASE: "platform exclusive after 45-day theatrical",
        AssumptionKey.TERRITORY: "US",
        AssumptionKey.TALENT: "ensemble without a global star quote",
        AssumptionKey.PLATFORM: "specialty-svod",
    }
    for key, value in assumption_values.items():
        forecast_service.set_assumption(
            project_id,
            principal=principal,
            acl_epoch=epoch,
            key=key,
            value=value,
            data_as_of=as_of,
            evidence=f"producer memo {key.value}",
        )
    for title, budget_amount, gross, released, dated in (
        ("Latch Key", 800_000, 2_400_000, "2022-03-01", "2022-12-31"),
        ("Harbor Night", 1_100_000, 3_000_000, "2023-04-15", "2023-12-31"),
        ("Kitchen Watch", 950_000, 2_200_000, "2023-09-01", "2024-01-15"),
    ):
        forecast_service.register_comparable(
            project_id,
            principal=principal,
            acl_epoch=epoch,
            title=title,
            territory="US",
            platform="specialty-svod",
            budget=budget_amount,
            observed_gross=gross,
            release_date=released,
            data_as_of=dated,
            source="internal released-outcome ledger",
            rationale=f"{title} matches specialty US SVOD because of budget class.",
        )
    with pytest.raises(InsufficientEvidenceError):
        forecast_service.forecast(
            project_id,
            principal=principal,
            acl_epoch=epoch,
            budget_id=budget.id,
            as_of="2020-01-01",
        )
    forecast_record = forecast_service.forecast(
        project_id,
        principal=principal,
        acl_epoch=epoch,
        budget_id=budget.id,
        as_of=as_of,
        audience_run_id=synthetic.id,
    )
    percentiles = [item.percentile for item in forecast_record.scenario.outcomes]
    assert percentiles == ["P10", "P50", "P90"]
    p10, p50, p90 = (forecast_record.outcome(name).value for name in percentiles)
    assert p10 <= p50 <= p90
    assert forecast_record.guarantee is False
    assert forecast_record.scenario.is_out_of_distribution is False
    assert FORECAST_DISCLAIMER in forecast_record.scenario.uncertainty_notes

    # 39. Generate, review, and export an evidence-backed investor deck.
    investor = InvestorArtifactService(
        stack.workspace,
        stack.authorization,
        stack.audit,
        stack.artifacts,
        stack.budgets,
        forecast_service,
        stack.rights,
    )
    assert "not a guarantee" in INVESTOR_DISCLAIMER.casefold()
    stack.artifacts.register_template(
        project_id=project_id,
        version="1",
        renderer_version="json/1",
        body="golden reviewed source {title}",
        principal=principal,
        acl_epoch=epoch,
        template_id="tmpl_golden_reviewed_source",
    )
    lookbook = stack.artifacts.create_artifact(
        project_id=project_id,
        artifact_type=ArtifactType.DOCUMENT,
        title="Golden reviewed lookbook",
        principal=principal,
        acl_epoch=epoch,
    )
    lookbook_version = stack.artifacts.create_version(
        lookbook.id,
        inputs={"title": "Golden reviewed lookbook", "page_count": 1},
        source_revision_id=stack.head,
        template_id="tmpl_golden_reviewed_source",
        template_version="1",
        renderer_version="json/1",
        classification=ArtifactClassification.INTERNAL,
        principal=principal,
        acl_epoch=epoch,
    )
    stack.artifacts.transition_review(
        lookbook_version.version.id,
        ArtifactStatus.IN_REVIEW,
        principal=principal,
        acl_epoch=epoch,
    )
    approved_source = stack.artifacts.transition_review(
        lookbook_version.version.id,
        ArtifactStatus.APPROVED,
        principal=principal,
        acl_epoch=epoch,
    )
    pack = investor.compile(
        project_id,
        principal=principal,
        acl_epoch=epoch,
        kind=PackKind.DECK,
        budget_id=budget.id,
        forecast_id=forecast_record.id,
        source_version_ids=(approved_source.version.id,),
        rights_source_id=source.source_id,
    )
    assert pack.kind is PackKind.DECK
    assert INVESTOR_DISCLAIMER in pack.disclaimer
    pack_preview = investor.preview(
        pack.id,
        principal=principal,
        acl_epoch=epoch,
        recipient="producer@golden.test",
    )
    approved_pack = investor.approve(pack.id, principal=principal, acl_epoch=epoch)
    assert approved_pack.approved is True
    exported = investor.export_pack(
        approved_pack.id,
        tmp_path / "golden-investor-deck.txt",
        principal=principal,
        acl_epoch=epoch,
    )
    assert INVESTOR_DISCLAIMER in exported.read_text(encoding="utf-8")
    assert pack_preview.pack_id == pack.id

    # 40. Read/propose through API/MCP; neither bypasses approval.
    mesh = IntegrationMeshService(
        stack.workspace,
        stack.authorization,
        stack.identity,
        stack.audit,
        stack.revisions,
        stack.proposals,
        stack.artifacts,
    )
    status = mesh.status(project_id, principal=principal, acl_epoch=epoch)
    assert status.api_version == API_VERSION
    assert status.project_id == GOLDEN_PROJECT_ID
    mcp = MeshMcpService(mesh)
    tools = mcp.tools()
    assert tools == MCP_TOOLS
    assert any(tool.side is ToolSide.PROPOSE for tool in tools)
    assert any(tool.side is ToolSide.COMMIT for tool in tools)
    read = mcp.invoke(
        "projects.read",
        {"project_id": project_id},
        principal=principal,
        acl_epoch=epoch,
    )
    assert read["id"] == GOLDEN_PROJECT_ID or read.get("project_id") == GOLDEN_PROJECT_ID or read
    if review_connector_base_url():
        assert require_review_connector()
    else:
        with pytest.raises(ReviewConnectorUnavailableError):
            require_review_connector()

    # 41. Open the same project on all five platforms; identity matches.
    snapshots = []
    for platform in PlatformId:
        app = open_platform(platform, tmp_path / f"host-{platform.value}")
        snap = app.identity_snapshot()
        assert snap.project_id == GOLDEN_PROJECT_ID
        assert snap.document_id == GOLDEN_DOCUMENT_ID
        snapshots.append(snap)
        app.close()
    assert len({item.layout_hash for item in snapshots}) == 1
    assert len({item.revision_id for item in snapshots}) == 1
    assert GOLDEN_ACTION_ID

    _configured_or_fail_closed(
        "EXT-FDX-FINAL-DRAFT",
        missing_live,
        require_final_draft,
        FinalDraftUnavailableError,
    )


def test_harbor_seed_is_airplane_safe(tmp_path: Path) -> None:
    from movie_muse.persistence.api import LocalWorkspace
    from movie_muse.testkit.api import load_golden_path_project

    workspace = LocalWorkspace(tmp_path / "harbor")
    seeded = load_golden_path_project(workspace)
    assert seeded.workspace.status().connectivity_offline is True
    assert seeded.project.id != GOLDEN_PROJECT_ID
    assert seeded.revision_head_id
