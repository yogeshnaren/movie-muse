"""Solo rooms never present fake humans; multi-writer attribution and ACL hold."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Role, make_human_actor
from movie_muse.room_mode.api import (
    FakeHumanError,
    ParticipantKind,
    RoomClosedError,
    RoomKind,
    RoomTeamMode,
    SoloAdmissionError,
    VoteValue,
)


def _start_solo(room_stack):
    return room_stack.rooms.start_room(
        project_id=room_stack.project.id,
        branch_id=room_stack.branch_id,
        revision_id=room_stack.document.base_revision_id,
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    )


def test_solo_room_has_one_human_and_simulated_seats_are_labeled(room_stack) -> None:
    session = _start_solo(room_stack)
    assert session.kind is RoomKind.SOLO
    humans = [item for item in session.participants if item.kind is ParticipantKind.HUMAN]
    assert len(humans) == 1
    seat = room_stack.rooms.add_simulated_seat(
        session.id,
        display_name="Beat timer",
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    )
    assert seat.kind is ParticipantKind.SIMULATED
    assert seat.presented_as_human is False
    roster = room_stack.rooms.visible_roster(session.id)
    kinds = {item["id"]: item["kind"] for item in roster}
    assert kinds[room_stack.owner.id] == "human"
    assert kinds[seat.id] == "simulated"
    with pytest.raises(FakeHumanError):
        room_stack.rooms.add_simulated_seat(
            session.id,
            display_name="Fake writer",
            principal=room_stack.principal,
            acl_epoch=room_stack.epoch,
            presented_as_human=True,
        )


def test_solo_room_rejects_second_human_writer(room_stack) -> None:
    session = _start_solo(room_stack)
    actor = make_human_actor(
        organization_id=room_stack.project.organization_id, display_name="Peer"
    )
    room_stack.identity.register_actor(actor)
    invitation = room_stack.identity.invite(
        inviter_actor_id=room_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=room_stack.project.id,
        role=Role.WRITER,
    )
    room_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    peer = room_stack.identity.principal(actor.id)
    with pytest.raises(SoloAdmissionError):
        room_stack.rooms.admit(
            session.id,
            peer=peer,
            principal=room_stack.principal,
            acl_epoch=room_stack.identity.acl_epoch(),
        )


def test_multi_writer_preserves_attribution_and_acl(room_stack) -> None:
    session = room_stack.rooms.start_room(
        project_id=room_stack.project.id,
        branch_id=room_stack.branch_id,
        revision_id=room_stack.document.base_revision_id,
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
        kind=RoomKind.MULTI_WRITER,
    )
    actor = make_human_actor(
        organization_id=room_stack.project.organization_id, display_name="CoWriter"
    )
    room_stack.identity.register_actor(actor)
    invitation = room_stack.identity.invite(
        inviter_actor_id=room_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=room_stack.project.id,
        role=Role.WRITER,
    )
    room_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    peer = room_stack.identity.principal(actor.id)
    admitted = room_stack.rooms.admit(
        session.id,
        peer=peer,
        principal=room_stack.principal,
        acl_epoch=room_stack.identity.acl_epoch(),
    )
    assert admitted.kind is ParticipantKind.HUMAN
    assert admitted.presented_as_human is True
    candidate = room_stack.rooms.capture(
        session.id,
        summary="Ada keeps the brass key",
        principal=peer,
        acl_epoch=room_stack.identity.acl_epoch(),
    )
    assert candidate.captured_by_actor_id == actor.id
    viewer_actor = make_human_actor(
        organization_id=room_stack.project.organization_id, display_name="Viewer"
    )
    room_stack.identity.register_actor(viewer_actor)
    viewer_invite = room_stack.identity.invite(
        inviter_actor_id=room_stack.owner.id,
        invitee_actor_id=viewer_actor.id,
        project_id=room_stack.project.id,
        role=Role.VIEWER,
    )
    room_stack.identity.accept_invitation(viewer_invite.id, actor_id=viewer_actor.id)
    viewer = room_stack.identity.principal(viewer_actor.id)
    with pytest.raises(AuthorizationError):
        room_stack.rooms.capture(
            session.id,
            summary="viewer must not capture",
            principal=viewer,
            acl_epoch=room_stack.identity.acl_epoch(),
        )


def test_timer_board_vote_and_close(room_stack) -> None:
    session = _start_solo(room_stack)
    timer = room_stack.rooms.start_timer(
        session.id,
        duration_seconds=60,
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    )
    assert room_stack.rooms.timer_remaining(session.id) == 60
    room_stack.clock.advance(25)
    assert room_stack.rooms.timer_remaining(session.id) == 35
    card = room_stack.rooms.add_card(
        session.id,
        text="Harbor night is the midpoint",
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    )
    assert room_stack.rooms.list_cards(session.id)[0].text == card.text
    room_stack.rooms.attach_proposal(
        session.id,
        proposal_id="prp_01TESTPROPOSAL000000000000",
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    )
    ballot = room_stack.rooms.vote(
        session.id,
        target_id=card.id,
        value=VoteValue.YES,
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    )
    assert ballot.value is VoteValue.YES
    ack = room_stack.rooms.acknowledge(
        session.id,
        target_id=card.id,
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    )
    assert ack.actor_id == room_stack.owner.id
    closed = room_stack.rooms.close_room(
        session.id,
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    )
    assert closed.status.value == "closed"
    with pytest.raises(RoomClosedError):
        room_stack.rooms.add_card(
            session.id,
            text="too late",
            principal=room_stack.principal,
            acl_epoch=room_stack.epoch,
        )
    assert timer.duration_seconds == 60


def test_research_team_mode_defaults_to_research_capture(room_stack) -> None:
    session = room_stack.rooms.start_room(
        project_id=room_stack.project.id,
        branch_id=room_stack.branch_id,
        revision_id=room_stack.document.base_revision_id,
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
        team_mode=RoomTeamMode.RESEARCH_TEAM,
    )
    candidate = room_stack.rooms.capture(
        session.id,
        summary="Harbor tide tables",
        principal=room_stack.principal,
        acl_epoch=room_stack.epoch,
    )
    assert candidate.kind.value == "research"
