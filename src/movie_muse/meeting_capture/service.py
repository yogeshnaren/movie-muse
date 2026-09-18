"""Consent-first meeting capture, transcript provenance, and Room Harvest."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from movie_muse.artifacts.api import (
    ArtifactClassification,
    ArtifactService,
    ArtifactType,
)
from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.identity.api import Principal, PrincipalKind
from movie_muse.meeting_capture.errors import (
    ConsentDeniedError,
    ConsentRequiredError,
    HarvestNotOpenError,
    HarvestRequiresReviewError,
    MeetingDeletedError,
    MeetingNotFoundError,
    RetentionExpiredError,
)
from movie_muse.meeting_capture.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.meeting_capture.types import (
    CaptureState,
    ConsentState,
    ConsentView,
    HarvestItem,
    HarvestItemState,
    MediaLink,
    MeetingSession,
    ProvenanceEntry,
    Utterance,
)
from movie_muse.persistence.api import utc_now
from movie_muse.project_memory.api import (
    MemoryCandidate,
    MemoryCandidateKind,
    ProjectMemory,
    ProjectMemoryService,
)
from movie_muse.schemas.api import new_ulid

TRANSCRIPT_TEMPLATE_ID = "tmpl_meeting_transcript"
TRANSCRIPT_TEMPLATE_VERSION = "1.0"
TRANSCRIPT_RENDERER = "deterministic-json/1"


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_iso(moment: datetime) -> str:
    aware = moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
    return aware.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class MeetingCaptureService:
    """Consent-visible capture. Transcript edits keep provenance. Harvest is reviewed."""

    def __init__(
        self,
        artifacts: ArtifactService,
        memory: ProjectMemoryService,
        authorization: AuthorizationService,
        audit: AuditLog,
        *,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.artifacts = artifacts
        self.memory = memory
        self.authorization = authorization
        self.audit = audit
        self.workspace = artifacts.workspace
        self.clock = clock

    def begin_session(
        self,
        *,
        project_id: str,
        branch_id: str,
        revision_id: str,
        principal: Principal,
        acl_epoch: int,
        room_id: str | None = None,
        retention_days: int = 30,
    ) -> MeetingSession:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        now = self.clock()
        session = MeetingSession(
            id=f"mtg_{new_ulid()}",
            project_id=project_id,
            branch_id=branch_id,
            revision_id=revision_id,
            consent_state=ConsentState.PENDING,
            capture_state=CaptureState.CONSENT_REQUIRED,
            created_at=now,
            created_by_actor_id=principal.actor_id,
            room_id=room_id,
            retention_until=_format_iso(_parse_iso(now) + timedelta(days=retention_days)),
        )
        stored = self._put_session(session)
        self._audit(principal, acl_epoch, "meeting.begin", stored.id, "consent_required")
        return stored

    def consent_view(self, meeting_id: str) -> ConsentView:
        session = self._load(meeting_id)
        return ConsentView(
            meeting_id=session.id,
            consent_state=session.consent_state,
            capture_state=session.capture_state,
            visible=True,
            actor_id=session.consent_actor_id,
            decided_at=session.consent_at,
        )

    def grant_consent(
        self,
        meeting_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> MeetingSession:
        session = self._usable(meeting_id, principal, acl_epoch, Action.PROPOSE)
        updated = self._replace(
            session,
            consent_state=ConsentState.GRANTED,
            consent_actor_id=principal.actor_id,
            consent_at=self.clock(),
        )
        self._audit(principal, acl_epoch, "meeting.consent_grant", meeting_id, "granted")
        return updated

    def deny_consent(
        self,
        meeting_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> MeetingSession:
        session = self._usable(meeting_id, principal, acl_epoch, Action.PROPOSE)
        updated = self._replace(
            session,
            consent_state=ConsentState.DENIED,
            capture_state=CaptureState.STOPPED,
            consent_actor_id=principal.actor_id,
            consent_at=self.clock(),
        )
        self._audit(principal, acl_epoch, "meeting.consent_deny", meeting_id, "denied")
        return updated

    def withdraw_consent(
        self,
        meeting_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> MeetingSession:
        session = self._usable(meeting_id, principal, acl_epoch, Action.PROPOSE)
        capture = (
            CaptureState.STOPPED
            if session.capture_state is CaptureState.RECORDING
            else session.capture_state
        )
        updated = self._replace(
            session,
            consent_state=ConsentState.WITHDRAWN,
            capture_state=capture,
            consent_actor_id=principal.actor_id,
            consent_at=self.clock(),
        )
        self._audit(principal, acl_epoch, "meeting.consent_withdraw", meeting_id, "withdrawn")
        return updated

    def start_recording(
        self,
        meeting_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> MeetingSession:
        session = self._consented(meeting_id, principal, acl_epoch)
        updated = self._replace(session, capture_state=CaptureState.RECORDING)
        self._audit(principal, acl_epoch, "meeting.record_start", meeting_id, "recording")
        return updated

    def stop_recording(
        self,
        meeting_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> MeetingSession:
        session = self._usable(meeting_id, principal, acl_epoch, Action.PROPOSE)
        updated = self._replace(session, capture_state=CaptureState.STOPPED)
        self._audit(principal, acl_epoch, "meeting.record_stop", meeting_id, "stopped")
        return updated

    def import_transcript(
        self,
        meeting_id: str,
        *,
        utterances: tuple[Utterance, ...],
        principal: Principal,
        acl_epoch: int,
        media_links: tuple[MediaLink, ...] = (),
    ) -> MeetingSession:
        session = self._consented(meeting_id, principal, acl_epoch)
        stamped = tuple(
            Utterance(
                id=item.id or f"utt_{new_ulid()}",
                speaker_label=item.speaker_label,
                start_ms=item.start_ms,
                end_ms=item.end_ms,
                text=item.text,
                speaker_actor_id=item.speaker_actor_id,
                provenance=(
                    *item.provenance,
                    ProvenanceEntry(
                        actor_id=principal.actor_id,
                        operation="import",
                        created_at=self.clock(),
                        note=item.speaker_label,
                    ),
                ),
            )
            for item in utterances
        )
        version = self._persist_transcript(session, stamped, media_links, principal, acl_epoch)
        updated = self._replace(
            session,
            capture_state=CaptureState.IMPORTED,
            artifact_id=version.version.artifact_id,
            artifact_version_id=version.version.id,
            utterances=stamped,
            media_links=media_links,
        )
        self._audit(principal, acl_epoch, "meeting.import", meeting_id, version.version.id)
        return updated

    def correct_speaker(
        self,
        meeting_id: str,
        utterance_id: str,
        *,
        speaker_label: str,
        principal: Principal,
        acl_epoch: int,
        speaker_actor_id: str | None = None,
    ) -> Utterance:
        session = self._consented(meeting_id, principal, acl_epoch)
        current = self._utterance(session, utterance_id)
        corrected = Utterance(
            id=current.id,
            speaker_label=speaker_label,
            start_ms=current.start_ms,
            end_ms=current.end_ms,
            text=current.text,
            speaker_actor_id=speaker_actor_id,
            provenance=(
                *current.provenance,
                ProvenanceEntry(
                    actor_id=principal.actor_id,
                    operation="correct_speaker",
                    created_at=self.clock(),
                    note=f"{current.speaker_label}->{speaker_label}",
                ),
            ),
        )
        self._rewrite_utterance(session, corrected, principal, acl_epoch)
        self._audit(principal, acl_epoch, "meeting.correct_speaker", utterance_id, speaker_label)
        return corrected

    def edit_utterance(
        self,
        meeting_id: str,
        utterance_id: str,
        *,
        text: str,
        principal: Principal,
        acl_epoch: int,
    ) -> Utterance:
        session = self._consented(meeting_id, principal, acl_epoch)
        current = self._utterance(session, utterance_id)
        edited = Utterance(
            id=current.id,
            speaker_label=current.speaker_label,
            start_ms=current.start_ms,
            end_ms=current.end_ms,
            text=text,
            speaker_actor_id=current.speaker_actor_id,
            provenance=(
                *current.provenance,
                ProvenanceEntry(
                    actor_id=principal.actor_id,
                    operation="edit_text",
                    created_at=self.clock(),
                    note=current.text,
                ),
            ),
        )
        self._rewrite_utterance(session, edited, principal, acl_epoch)
        self._audit(principal, acl_epoch, "meeting.edit_utterance", utterance_id, text)
        return edited

    def add_media_link(
        self,
        meeting_id: str,
        *,
        title: str,
        uri: str,
        start_ms: int,
        principal: Principal,
        acl_epoch: int,
        utterance_id: str | None = None,
    ) -> MediaLink:
        session = self._consented(meeting_id, principal, acl_epoch)
        link = MediaLink(
            id=f"mlk_{new_ulid()}",
            title=title,
            uri=uri,
            start_ms=start_ms,
            artifact_id=session.artifact_id,
            utterance_id=utterance_id,
        )
        self._replace(session, media_links=(*session.media_links, link))
        return link

    def search(
        self,
        meeting_id: str,
        query: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[Utterance | MediaLink, ...]:
        session = self.get_session(meeting_id, principal=principal, acl_epoch=acl_epoch)
        needle = query.casefold()
        hits: list[Utterance | MediaLink] = []
        for item in session.utterances:
            if needle in item.text.casefold() or needle in item.speaker_label.casefold():
                hits.append(item)
        for link in session.media_links:
            if needle in link.title.casefold() or needle in link.uri.casefold():
                hits.append(link)
        return tuple(hits)

    def extract_candidate(
        self,
        meeting_id: str,
        *,
        summary: str,
        principal: Principal,
        acl_epoch: int,
        kind: MemoryCandidateKind = MemoryCandidateKind.IDEA,
        utterance_id: str | None = None,
        auto_promote: bool = False,
    ) -> MemoryCandidate:
        if auto_promote:
            raise HarvestRequiresReviewError("meeting candidates never become canon automatically")
        session = self._consented(meeting_id, principal, acl_epoch)
        candidate = self.memory.capture(
            project_id=session.project_id,
            kind=kind,
            summary=summary,
            principal=principal,
            acl_epoch=acl_epoch,
            branch_id=session.branch_id,
            revision_id=session.revision_id,
            artifact_id=session.artifact_id,
        )
        item = HarvestItem(
            candidate_id=candidate.id,
            state=HarvestItemState.CAPTURED,
            utterance_id=utterance_id,
        )
        self._replace(session, harvest=(*session.harvest, item))
        self._audit(principal, acl_epoch, "meeting.extract", candidate.id, meeting_id)
        return candidate

    def start_harvest_review(
        self,
        meeting_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[HarvestItem, ...]:
        session = self._usable(meeting_id, principal, acl_epoch, Action.ACCEPT)
        if principal.kind is not PrincipalKind.HUMAN:
            raise HarvestRequiresReviewError("only a human may open meeting harvest review")
        reviewed = tuple(
            HarvestItem(
                candidate_id=item.candidate_id,
                state=(
                    HarvestItemState.UNDER_REVIEW
                    if item.state is HarvestItemState.CAPTURED
                    else item.state
                ),
                utterance_id=item.utterance_id,
            )
            for item in session.harvest
        )
        updated = self._replace(session, harvest=reviewed, harvest_open=True)
        self._audit(principal, acl_epoch, "meeting.harvest_review", meeting_id, str(len(reviewed)))
        return updated.harvest

    def harvest_promote(
        self,
        meeting_id: str,
        candidate_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> ProjectMemory:
        session = self._usable(meeting_id, principal, acl_epoch, Action.ACCEPT)
        if not session.harvest_open:
            raise HarvestNotOpenError("start_harvest_review before promoting")
        item = self._harvest_item(session, candidate_id)
        if item.state is not HarvestItemState.UNDER_REVIEW:
            raise HarvestNotOpenError(f"harvest item is {item.state.value}")
        memory = self.memory.promote(candidate_id, principal=principal, acl_epoch=acl_epoch)
        self._set_harvest_state(session, candidate_id, HarvestItemState.PROMOTED)
        self._audit(principal, acl_epoch, "meeting.harvest_promote", candidate_id, memory.id)
        return memory

    def harvest_discard(
        self,
        meeting_id: str,
        candidate_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        note: str = "",
    ) -> MemoryCandidate:
        session = self._usable(meeting_id, principal, acl_epoch, Action.ACCEPT)
        if not session.harvest_open:
            raise HarvestNotOpenError("start_harvest_review before discarding")
        rejected = self.memory.reject(
            candidate_id, principal=principal, acl_epoch=acl_epoch, note=note
        )
        self._set_harvest_state(session, candidate_id, HarvestItemState.DISCARDED)
        self._audit(principal, acl_epoch, "meeting.harvest_discard", candidate_id, note)
        return rejected

    def get_session(
        self,
        meeting_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> MeetingSession:
        session = self._load(meeting_id)
        self._require(principal, Action.READ, session.project_id, acl_epoch)
        if session.capture_state is CaptureState.DELETED:
            raise MeetingDeletedError(f"meeting {meeting_id} was deleted")
        self._enforce_retention(session)
        return session

    def list_utterances(self, meeting_id: str) -> tuple[Utterance, ...]:
        return self._load(meeting_id).utterances

    def delete_session(
        self,
        meeting_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> MeetingSession:
        session = self._usable(meeting_id, principal, acl_epoch, Action.ACCEPT)
        updated = self._replace(
            session,
            capture_state=CaptureState.DELETED,
            utterances=(),
            media_links=(),
        )
        self._audit(principal, acl_epoch, "meeting.delete", meeting_id, "deleted")
        return updated

    def _consented(
        self, meeting_id: str, principal: Principal, acl_epoch: int
    ) -> MeetingSession:
        session = self._usable(meeting_id, principal, acl_epoch, Action.PROPOSE)
        if session.consent_state is ConsentState.DENIED:
            raise ConsentDeniedError("consent was denied")
        if session.consent_state is ConsentState.WITHDRAWN:
            raise ConsentDeniedError("consent was withdrawn")
        if session.consent_state is not ConsentState.GRANTED:
            raise ConsentRequiredError("recording consent must be granted and visible")
        return session

    def _usable(
        self,
        meeting_id: str,
        principal: Principal,
        acl_epoch: int,
        action: Action,
    ) -> MeetingSession:
        session = self._load(meeting_id)
        self._require(principal, action, session.project_id, acl_epoch)
        if session.capture_state is CaptureState.DELETED:
            raise MeetingDeletedError(f"meeting {meeting_id} was deleted")
        self._enforce_retention(session)
        return session

    def _enforce_retention(self, session: MeetingSession) -> None:
        if session.retention_until is None:
            return
        if _parse_iso(self.clock()) > _parse_iso(session.retention_until):
            raise RetentionExpiredError(f"meeting {session.id} retention elapsed")

    def _load(self, meeting_id: str) -> MeetingSession:
        index = load_index(self.workspace)
        digest = dict(index.get("session_digests", {})).get(meeting_id)
        if digest is None:
            raise MeetingNotFoundError(f"meeting {meeting_id} is not in the index")
        return MeetingSession.from_dict(load_payload(self.workspace, str(digest)))

    def _put_session(self, session: MeetingSession) -> MeetingSession:
        def persist(index: dict[str, Any]) -> MeetingSession:
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

    def _replace(self, session: MeetingSession, **changes: Any) -> MeetingSession:
        payload = session.to_dict()
        for key, value in changes.items():
            if isinstance(value, tuple):
                payload[key] = [
                    item.to_dict() if hasattr(item, "to_dict") else item for item in value
                ]
            elif isinstance(value, Enum):
                payload[key] = value.value
            else:
                payload[key] = value
        return self._put_session(MeetingSession.from_dict(payload))

    def _utterance(self, session: MeetingSession, utterance_id: str) -> Utterance:
        for item in session.utterances:
            if item.id == utterance_id:
                return item
        raise MeetingNotFoundError(f"utterance {utterance_id} is not in {session.id}")

    def _rewrite_utterance(
        self,
        session: MeetingSession,
        updated: Utterance,
        principal: Principal,
        acl_epoch: int,
    ) -> MeetingSession:
        utterances = tuple(
            updated if item.id == updated.id else item for item in session.utterances
        )
        version = self._persist_transcript(
            session, utterances, session.media_links, principal, acl_epoch
        )
        return self._replace(
            session,
            utterances=utterances,
            artifact_version_id=version.version.id,
        )

    def _persist_transcript(
        self,
        session: MeetingSession,
        utterances: tuple[Utterance, ...],
        media_links: tuple[MediaLink, ...],
        principal: Principal,
        acl_epoch: int,
    ) -> Any:
        self._ensure_template(session.project_id, principal, acl_epoch)
        artifact_id = session.artifact_id
        if artifact_id is None:
            artifact = self.artifacts.create_artifact(
                project_id=session.project_id,
                artifact_type=ArtifactType.DOCUMENT,
                title=f"Meeting {session.id}",
                principal=principal,
                acl_epoch=acl_epoch,
            )
            artifact_id = artifact.id
            session = self._replace(session, artifact_id=artifact_id)
        return self.artifacts.create_version(
            artifact_id,
            inputs={
                "utterances": [item.to_dict() for item in utterances],
                "media_links": [item.to_dict() for item in media_links],
            },
            source_revision_id=session.revision_id,
            template_id=TRANSCRIPT_TEMPLATE_ID,
            template_version=TRANSCRIPT_TEMPLATE_VERSION,
            renderer_version=TRANSCRIPT_RENDERER,
            classification=ArtifactClassification.RESTRICTED,
            principal=principal,
            acl_epoch=acl_epoch,
        )

    def _ensure_template(self, project_id: str, principal: Principal, acl_epoch: int) -> None:
        index = load_index(self.workspace)
        if dict(index.get("template_ids", {})).get(project_id) == TRANSCRIPT_TEMPLATE_ID:
            return
        self.artifacts.register_template(
            project_id=project_id,
            template_id=TRANSCRIPT_TEMPLATE_ID,
            version=TRANSCRIPT_TEMPLATE_VERSION,
            renderer_version=TRANSCRIPT_RENDERER,
            body="{{ source_revision }} :: {{ inputs }}",
            principal=principal,
            acl_epoch=acl_epoch,
        )

        def persist(index: dict[str, Any]) -> None:
            templates = dict(index["template_ids"])
            templates[project_id] = TRANSCRIPT_TEMPLATE_ID
            index["template_ids"] = templates

        mutate_index(self.workspace, persist)

    def _harvest_item(self, session: MeetingSession, candidate_id: str) -> HarvestItem:
        for item in session.harvest:
            if item.candidate_id == candidate_id:
                return item
        raise HarvestNotOpenError(f"candidate {candidate_id} is not in meeting harvest")

    def _set_harvest_state(
        self, session: MeetingSession, candidate_id: str, state: HarvestItemState
    ) -> None:
        harvest = tuple(
            HarvestItem(
                candidate_id=item.candidate_id,
                state=state if item.candidate_id == candidate_id else item.state,
                utterance_id=item.utterance_id,
            )
            for item in session.harvest
        )
        self._replace(self._load(session.id), harvest=harvest)

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
            object_kind="meeting_session",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
