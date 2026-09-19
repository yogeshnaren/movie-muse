"""Permissioned Room Mode: solo/multi sessions, boards, harvest review."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.identity.api import Principal, PrincipalKind
from movie_muse.persistence.api import utc_now
from movie_muse.project_memory.api import (
    MemoryCandidate,
    MemoryCandidateKind,
    ProjectMemory,
    ProjectMemoryService,
)
from movie_muse.room_mode.errors import (
    FakeHumanError,
    HarvestNotOpenError,
    HarvestRequiresReviewError,
    RoomClosedError,
    RoomNotFoundError,
    SoloAdmissionError,
    UnknownParticipantError,
)
from movie_muse.room_mode.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.room_mode.types import (
    BoardCard,
    HarvestItem,
    HarvestItemState,
    ParticipantKind,
    RoomAck,
    RoomKind,
    RoomParticipant,
    RoomRole,
    RoomSession,
    RoomStatus,
    RoomTeamMode,
    RoomTimer,
    RoomVote,
    VoteValue,
)
from movie_muse.schemas.api import (
    CollaborationEvent,
    CollaborationRecordKind,
    PromotionState,
    new_id,
    new_ulid,
)

_KIND_TO_RECORD = {
    MemoryCandidateKind.IDEA: CollaborationRecordKind.IDEA,
    MemoryCandidateKind.DECISION: CollaborationRecordKind.DECISION,
    MemoryCandidateKind.QUESTION: CollaborationRecordKind.QUESTION,
    MemoryCandidateKind.RESEARCH: CollaborationRecordKind.RESEARCH_REQUEST,
    MemoryCandidateKind.ASSIGNMENT: CollaborationRecordKind.ASSIGNMENT,
    MemoryCandidateKind.FACT: CollaborationRecordKind.CHARACTER_FACT,
    MemoryCandidateKind.REJECTED_IDEA: CollaborationRecordKind.REJECTED_IDEA,
}


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_iso(moment: datetime) -> str:
    aware = moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
    return aware.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class RoomModeService:
    """Physical-room sessions. Simulated seats are never presented as humans."""

    def __init__(
        self,
        memory: ProjectMemoryService,
        authorization: AuthorizationService,
        audit: AuditLog,
        *,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.memory = memory
        self.authorization = authorization
        self.audit = audit
        self.workspace = memory.workspace
        self.clock = clock

    def start_room(
        self,
        *,
        project_id: str,
        branch_id: str,
        revision_id: str,
        principal: Principal,
        acl_epoch: int,
        kind: RoomKind = RoomKind.SOLO,
        team_mode: RoomTeamMode = RoomTeamMode.WRITER,
    ) -> RoomSession:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        now = self.clock()
        facilitator = RoomParticipant(
            id=principal.actor_id,
            display_name=principal.display_name or principal.actor_id,
            kind=ParticipantKind.HUMAN,
            role=RoomRole.FACILITATOR,
            presented_as_human=True,
            actor_id=principal.actor_id,
        )
        session = RoomSession(
            id=f"room_{new_ulid()}",
            project_id=project_id,
            branch_id=branch_id,
            revision_id=revision_id,
            kind=kind,
            team_mode=team_mode,
            status=RoomStatus.OPEN,
            facilitator_actor_id=principal.actor_id,
            started_at=now,
            participants=(facilitator,),
        )
        stored = self._put_session(session)
        self._audit(principal, acl_epoch, "room_mode.start", stored.id, stored.kind.value)
        return stored

    def add_simulated_seat(
        self,
        room_id: str,
        *,
        display_name: str,
        principal: Principal,
        acl_epoch: int,
        role: RoomRole = RoomRole.WRITER,
        presented_as_human: bool = False,
    ) -> RoomParticipant:
        session = self._open_session(room_id, principal, acl_epoch, Action.PROPOSE)
        if presented_as_human:
            raise FakeHumanError("simulated seats must not be presented as human participants")
        seat = RoomParticipant(
            id=f"sim_{new_ulid()}",
            display_name=display_name,
            kind=ParticipantKind.SIMULATED,
            role=role,
            presented_as_human=False,
        )
        updated = self._replace_session(
            session,
            participants=(*session.participants, seat),
        )
        self._audit(principal, acl_epoch, "room_mode.simulated_seat", updated.id, seat.id)
        return seat

    def admit(
        self,
        room_id: str,
        *,
        peer: Principal,
        principal: Principal,
        acl_epoch: int,
        role: RoomRole = RoomRole.WRITER,
    ) -> RoomParticipant:
        session = self._open_session(room_id, principal, acl_epoch, Action.PROPOSE)
        self._require(peer, Action.READ, session.project_id, acl_epoch)
        if peer.kind is not PrincipalKind.HUMAN:
            raise FakeHumanError("only human principals may be admitted as writers")
        if session.kind is RoomKind.SOLO:
            raise SoloAdmissionError("solo rooms cannot admit a second human writer")
        if any(item.actor_id == peer.actor_id for item in session.participants):
            existing = next(
                item for item in session.participants if item.actor_id == peer.actor_id
            )
            return existing
        guest = RoomParticipant(
            id=peer.actor_id,
            display_name=peer.display_name or peer.actor_id,
            kind=ParticipantKind.HUMAN,
            role=role,
            presented_as_human=True,
            actor_id=peer.actor_id,
        )
        self._replace_session(session, participants=(*session.participants, guest))
        self._audit(principal, acl_epoch, "room_mode.admit", room_id, peer.actor_id)
        return guest

    def list_participants(self, room_id: str) -> tuple[RoomParticipant, ...]:
        return self.get_session(room_id).participants

    def visible_roster(self, room_id: str) -> tuple[dict[str, str], ...]:
        """UI roster. Simulated seats are labeled simulated, never human."""

        roster: list[dict[str, str]] = []
        for item in self.list_participants(room_id):
            label = "human" if item.kind is ParticipantKind.HUMAN else "simulated"
            roster.append(
                {
                    "id": item.id,
                    "display_name": item.display_name,
                    "kind": label,
                    "role": item.role.value,
                }
            )
        return tuple(roster)

    def start_timer(
        self,
        room_id: str,
        *,
        duration_seconds: int,
        principal: Principal,
        acl_epoch: int,
    ) -> RoomTimer:
        session = self._open_session(room_id, principal, acl_epoch, Action.PROPOSE)
        started_at = self.clock()
        started = _parse_iso(started_at)
        timer = RoomTimer(
            duration_seconds=duration_seconds,
            started_at=started_at,
            ends_at=_format_iso(started + timedelta(seconds=duration_seconds)),
        )
        self._replace_session(session, timer=timer)
        return timer

    def timer_remaining(self, room_id: str, *, now: str | None = None) -> int:
        session = self.get_session(room_id)
        if session.timer is None:
            return 0
        moment = _parse_iso(now or self.clock())
        remaining = int((_parse_iso(session.timer.ends_at) - moment).total_seconds())
        return max(0, remaining)

    def add_card(
        self,
        room_id: str,
        *,
        text: str,
        principal: Principal,
        acl_epoch: int,
        column: str = "ideas",
        author_participant_id: str | None = None,
    ) -> BoardCard:
        session = self._open_session(room_id, principal, acl_epoch, Action.PROPOSE)
        author = author_participant_id or principal.actor_id
        if author not in {item.id for item in session.participants}:
            raise UnknownParticipantError(f"participant {author} is not in room {room_id}")
        card = BoardCard(
            id=f"card_{new_ulid()}",
            room_id=room_id,
            text=text,
            author_participant_id=author,
            column=column,
            created_at=self.clock(),
        )

        def persist(index: dict[str, Any]) -> BoardCard:
            digest = put_payload(self.workspace, card.to_dict())
            ids = list(index["card_ids"])
            ids.append(card.id)
            index["card_ids"] = ids
            digests = dict(index["card_digests"])
            digests[card.id] = digest
            index["card_digests"] = digests
            return card

        stored = mutate_index(self.workspace, persist)
        self._audit(principal, acl_epoch, "room_mode.card", stored.id, room_id)
        return stored

    def list_cards(self, room_id: str) -> tuple[BoardCard, ...]:
        index = load_index(self.workspace)
        cards: list[BoardCard] = []
        for card_id in index.get("card_ids", ()):
            digest = index["card_digests"][card_id]
            card = BoardCard.from_dict(load_payload(self.workspace, str(digest)))
            if card.room_id == room_id:
                cards.append(card)
        return tuple(cards)

    def capture(
        self,
        room_id: str,
        *,
        summary: str,
        principal: Principal,
        acl_epoch: int,
        kind: MemoryCandidateKind | None = None,
        auto_promote: bool = False,
    ) -> MemoryCandidate:
        if auto_promote:
            raise HarvestRequiresReviewError("Room Harvest requires explicit review")
        session = self._open_session(room_id, principal, acl_epoch, Action.PROPOSE)
        mapped = kind or (
            MemoryCandidateKind.RESEARCH
            if session.team_mode is RoomTeamMode.RESEARCH_TEAM
            else MemoryCandidateKind.IDEA
        )
        event = CollaborationEvent(
            id=new_id("collaboration_event"),
            project_id=session.project_id,
            source="room_mode",
            record_kind=_KIND_TO_RECORD.get(mapped, CollaborationRecordKind.IDEA),
            summary=summary,
            captured_at=self.clock(),
            speaker_actor_id=principal.actor_id,
            promotion_state=PromotionState.CAPTURED,
        )
        candidate = self.memory.capture(
            project_id=session.project_id,
            kind=mapped,
            summary=summary,
            principal=principal,
            acl_epoch=acl_epoch,
            branch_id=session.branch_id,
            revision_id=session.revision_id,
            source_collaboration_event_id=event.id,
        )
        item = HarvestItem(
            event_id=event.id,
            candidate_id=candidate.id,
            state=HarvestItemState.CAPTURED,
        )

        def persist(index: dict[str, Any]) -> None:
            events = dict(index["events"])
            events[event.id] = event.to_dict()
            index["events"] = events
            harvest = dict(index["harvest_by_room"])
            rows = list(harvest.get(room_id, []))
            rows.append(item.to_dict())
            harvest[room_id] = rows
            index["harvest_by_room"] = harvest

        mutate_index(self.workspace, persist)
        self._audit(principal, acl_epoch, "room_mode.capture", candidate.id, room_id)
        return candidate

    def attach_proposal(
        self,
        room_id: str,
        *,
        proposal_id: str,
        principal: Principal,
        acl_epoch: int,
    ) -> RoomSession:
        session = self._open_session(room_id, principal, acl_epoch, Action.PROPOSE)
        if proposal_id in session.proposal_ids:
            return session
        return self._replace_session(
            session, proposal_ids=(*session.proposal_ids, proposal_id)
        )

    def vote(
        self,
        room_id: str,
        *,
        target_id: str,
        value: VoteValue,
        principal: Principal,
        acl_epoch: int,
    ) -> RoomVote:
        self._open_session(room_id, principal, acl_epoch, Action.PROPOSE)
        ballot = RoomVote(
            id=f"vote_{new_ulid()}",
            room_id=room_id,
            target_id=target_id,
            actor_id=principal.actor_id,
            value=value,
            created_at=self.clock(),
        )

        def persist(index: dict[str, Any]) -> RoomVote:
            votes = list(index["votes"])
            votes.append(ballot.to_dict())
            index["votes"] = votes
            return ballot

        stored = mutate_index(self.workspace, persist)
        self._audit(principal, acl_epoch, "room_mode.vote", stored.id, target_id)
        return stored

    def acknowledge(
        self,
        room_id: str,
        *,
        target_id: str,
        principal: Principal,
        acl_epoch: int,
    ) -> RoomAck:
        self._open_session(room_id, principal, acl_epoch, Action.COMMENT)
        ack = RoomAck(
            id=f"ack_{new_ulid()}",
            room_id=room_id,
            target_id=target_id,
            actor_id=principal.actor_id,
            created_at=self.clock(),
        )

        def persist(index: dict[str, Any]) -> RoomAck:
            acks = list(index["acks"])
            acks.append(ack.to_dict())
            index["acks"] = acks
            return ack

        stored = mutate_index(self.workspace, persist)
        self._audit(principal, acl_epoch, "room_mode.ack", stored.id, target_id)
        return stored

    def list_votes(self, room_id: str) -> tuple[RoomVote, ...]:
        index = load_index(self.workspace)
        return tuple(
            RoomVote.from_dict(item)
            for item in index.get("votes", ())
            if str(item.get("room_id")) == room_id
        )

    def list_acks(self, room_id: str) -> tuple[RoomAck, ...]:
        index = load_index(self.workspace)
        return tuple(
            RoomAck.from_dict(item)
            for item in index.get("acks", ())
            if str(item.get("room_id")) == room_id
        )

    def start_harvest_review(
        self,
        room_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[HarvestItem, ...]:
        session = self._open_session(room_id, principal, acl_epoch, Action.ACCEPT)
        if principal.kind is not PrincipalKind.HUMAN:
            raise HarvestRequiresReviewError("only a human may open Room Harvest review")
        self._replace_session(session, status=RoomStatus.HARVESTING)

        def persist(index: dict[str, Any]) -> tuple[HarvestItem, ...]:
            harvest = dict(index["harvest_by_room"])
            rows = []
            updated: list[dict[str, Any]] = []
            events = dict(index["events"])
            for raw in harvest.get(room_id, []):
                item = HarvestItem.from_dict(raw)
                if item.state is HarvestItemState.CAPTURED:
                    item = HarvestItem(
                        event_id=item.event_id,
                        candidate_id=item.candidate_id,
                        state=HarvestItemState.UNDER_REVIEW,
                    )
                    event = CollaborationEvent.from_dict(events[item.event_id])
                    events[item.event_id] = CollaborationEvent(
                        id=event.id,
                        project_id=event.project_id,
                        source=event.source,
                        record_kind=event.record_kind,
                        summary=event.summary,
                        captured_at=event.captured_at,
                        speaker_actor_id=event.speaker_actor_id,
                        promotion_state=PromotionState.UNDER_REVIEW,
                        promoted_project_memory_id=event.promoted_project_memory_id,
                    ).to_dict()
                rows.append(item)
                updated.append(item.to_dict())
            harvest[room_id] = updated
            index["harvest_by_room"] = harvest
            index["events"] = events
            return tuple(rows)

        items = mutate_index(self.workspace, persist)
        self._audit(principal, acl_epoch, "room_mode.harvest_review", room_id, str(len(items)))
        return items

    def harvest_promote(
        self,
        room_id: str,
        candidate_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> ProjectMemory:
        session = self.get_session(room_id)
        self._require(principal, Action.ACCEPT, session.project_id, acl_epoch)
        if session.status is not RoomStatus.HARVESTING:
            raise HarvestNotOpenError("start_harvest_review before promoting")
        item = self._harvest_item(room_id, candidate_id)
        if item.state is not HarvestItemState.UNDER_REVIEW:
            raise HarvestNotOpenError(f"harvest item is {item.state.value}")
        memory = self.memory.promote(candidate_id, principal=principal, acl_epoch=acl_epoch)
        self._set_harvest_state(
            room_id,
            candidate_id,
            HarvestItemState.PROMOTED,
            PromotionState.PROMOTED,
            promoted_memory_id=memory.id,
        )
        self._audit(principal, acl_epoch, "room_mode.harvest_promote", candidate_id, memory.id)
        return memory

    def harvest_discard(
        self,
        room_id: str,
        candidate_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        note: str = "",
    ) -> MemoryCandidate:
        session = self.get_session(room_id)
        self._require(principal, Action.ACCEPT, session.project_id, acl_epoch)
        if session.status is not RoomStatus.HARVESTING:
            raise HarvestNotOpenError("start_harvest_review before discarding")
        rejected = self.memory.reject(
            candidate_id, principal=principal, acl_epoch=acl_epoch, note=note
        )
        self._set_harvest_state(
            room_id, candidate_id, HarvestItemState.DISCARDED, PromotionState.DISCARDED
        )
        self._audit(principal, acl_epoch, "room_mode.harvest_discard", candidate_id, note)
        return rejected

    def list_harvest(self, room_id: str) -> tuple[HarvestItem, ...]:
        index = load_index(self.workspace)
        return tuple(
            HarvestItem.from_dict(item)
            for item in index.get("harvest_by_room", {}).get(room_id, ())
        )

    def close_room(
        self,
        room_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> RoomSession:
        session = self._open_session(room_id, principal, acl_epoch, Action.PROPOSE)
        return self._replace_session(
            session, status=RoomStatus.CLOSED, ended_at=self.clock()
        )

    def get_session(self, room_id: str) -> RoomSession:
        index = load_index(self.workspace)
        digest = dict(index.get("session_digests", {})).get(room_id)
        if digest is None:
            raise RoomNotFoundError(f"room {room_id} is not in the index")
        return RoomSession.from_dict(load_payload(self.workspace, str(digest)))

    def _open_session(
        self,
        room_id: str,
        principal: Principal,
        acl_epoch: int,
        action: Action,
    ) -> RoomSession:
        session = self.get_session(room_id)
        self._require(principal, action, session.project_id, acl_epoch)
        if session.status is RoomStatus.CLOSED:
            raise RoomClosedError(f"room {room_id} is closed")
        return session

    def _put_session(self, session: RoomSession) -> RoomSession:
        def persist(index: dict[str, Any]) -> RoomSession:
            digest = put_payload(self.workspace, session.to_dict())
            ids = list(index["session_ids"])
            if session.id not in ids:
                ids.append(session.id)
            index["session_ids"] = ids
            digests = dict(index["session_digests"])
            digests[session.id] = digest
            index["session_digests"] = digests
            return session

        return mutate_index(self.workspace, persist)

    def _replace_session(
        self,
        session: RoomSession,
        *,
        participants: tuple[RoomParticipant, ...] | None = None,
        status: RoomStatus | None = None,
        timer: RoomTimer | None = None,
        proposal_ids: tuple[str, ...] | None = None,
        ended_at: str | None = None,
    ) -> RoomSession:
        updated = RoomSession(
            id=session.id,
            project_id=session.project_id,
            branch_id=session.branch_id,
            revision_id=session.revision_id,
            kind=session.kind,
            team_mode=session.team_mode,
            status=status or session.status,
            facilitator_actor_id=session.facilitator_actor_id,
            started_at=session.started_at,
            participants=participants if participants is not None else session.participants,
            ended_at=ended_at if ended_at is not None else session.ended_at,
            timer=timer if timer is not None else session.timer,
            proposal_ids=proposal_ids if proposal_ids is not None else session.proposal_ids,
        )
        return self._put_session(updated)

    def _harvest_item(self, room_id: str, candidate_id: str) -> HarvestItem:
        for item in self.list_harvest(room_id):
            if item.candidate_id == candidate_id:
                return item
        raise HarvestNotOpenError(f"candidate {candidate_id} is not in room harvest")

    def _set_harvest_state(
        self,
        room_id: str,
        candidate_id: str,
        state: HarvestItemState,
        promotion: PromotionState,
        *,
        promoted_memory_id: str | None = None,
    ) -> None:
        def persist(index: dict[str, Any]) -> None:
            harvest = dict(index["harvest_by_room"])
            events = dict(index["events"])
            updated = []
            for raw in harvest.get(room_id, []):
                item = HarvestItem.from_dict(raw)
                if item.candidate_id == candidate_id:
                    item = HarvestItem(
                        event_id=item.event_id,
                        candidate_id=item.candidate_id,
                        state=state,
                    )
                    event = CollaborationEvent.from_dict(events[item.event_id])
                    events[item.event_id] = CollaborationEvent(
                        id=event.id,
                        project_id=event.project_id,
                        source=event.source,
                        record_kind=event.record_kind,
                        summary=event.summary,
                        captured_at=event.captured_at,
                        speaker_actor_id=event.speaker_actor_id,
                        promotion_state=promotion,
                        promoted_project_memory_id=promoted_memory_id,
                    ).to_dict()
                updated.append(item.to_dict())
            harvest[room_id] = updated
            index["harvest_by_room"] = harvest
            index["events"] = events

        mutate_index(self.workspace, persist)

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )

    def _audit(
        self,
        principal: Principal,
        acl_epoch: int,
        operation: str,
        object_id: str,
        reason: str,
    ) -> None:
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=operation,
            object_kind="room_session",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
