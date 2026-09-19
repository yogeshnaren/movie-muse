"""Live platform sessions over shared domain contracts. Hosts stay thin."""

from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from movie_muse.artifacts.api import ArtifactService
from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.editor.api import EditorService, SceneCard
from movie_muse.identity.api import Actor, IdentityService, Organization, Principal, PrincipalKind
from movie_muse.layout.api import LAYOUT_ENGINE_VERSION, LayoutService
from movie_muse.meeting_capture.api import ConsentState, MeetingCaptureService
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.platforms.errors import (
    CaptureConsentError,
    DeepLinkError,
    LongFormUnavailableError,
    StaticMockError,
)
from movie_muse.platforms.golden import (
    GOLDEN_ACTION_ID,
    GOLDEN_ACTOR_ID,
    GOLDEN_BRANCH_ID,
    GOLDEN_DOCUMENT_ID,
    GOLDEN_PROJECT_ID,
    golden_project_and_document,
)
from movie_muse.platforms.parity import capabilities_for
from movie_muse.platforms.storage import WEB_DEFAULT_ORIGIN, prepare_storage
from movie_muse.platforms.types import (
    ANNOTATION_BUDGET_SECONDS,
    DEEP_LINK_SCHEME,
    MIN_TOUCH_TARGET_PT,
    MOBILE_PLATFORMS,
    UPDATE_CHANNEL,
    AccessibilityBudget,
    AnnotationResult,
    PlatformCapabilities,
    PlatformId,
    PlatformIdentity,
    StorageProfile,
)
from movie_muse.project_memory.api import ProjectMemoryService
from movie_muse.revisions.api import RevisionService
from movie_muse.room_mode.api import RoomKind, RoomModeService, RoomTeamMode
from movie_muse.sync.api import SyncProtocol, SyncUploadBlockedError


class PlatformApp:
    """One live host session. Not a static mock: every call hits a workspace."""

    def __init__(
        self,
        platform: PlatformId,
        home: Path,
        *,
        origin: str = WEB_DEFAULT_ORIGIN,
        resume: bool = False,
    ) -> None:
        self.platform = platform
        self.home = Path(home)
        self.origin = origin
        self.storage: StorageProfile = prepare_storage(platform, self.home, origin=origin)
        root = Path(self.storage.root)
        self.workspace = LocalWorkspace(root)
        project, document, branch_id = golden_project_and_document()
        self.identity = IdentityService(self.workspace)
        if resume:
            if self.workspace.store.get_meta("active_project_id") != GOLDEN_PROJECT_ID:
                raise StaticMockError("resume requires a previously opened golden workspace")
        else:
            self.workspace.open_project(project, document, branch_id=branch_id)
            owner = Actor(
                id=GOLDEN_ACTOR_ID,
                display_name="Owner",
                principal_kind=PrincipalKind.HUMAN,
                organization_id=project.organization_id,
                created_at="2026-09-01T00:00:00Z",
            )
            self.identity.bootstrap(
                organization=Organization(
                    id=project.organization_id,
                    name="Golden Studio",
                    created_at="2026-09-01T00:00:00Z",
                ),
                project=project,
                owner=owner,
            )
        self.audit = AuditLog(self.workspace)
        self.authorization = AuthorizationService(self.workspace, self.identity, audit=self.audit)
        self.revisions = RevisionService(self.workspace)
        self.revisions.bind(actor_id=GOLDEN_ACTOR_ID)
        self.editor = EditorService(self.revisions, actor_id=GOLDEN_ACTOR_ID)
        self.layout = LayoutService()
        self.sync = SyncProtocol(self.workspace)
        self.memory = ProjectMemoryService(self.workspace, self.authorization, self.audit)
        self.rooms = RoomModeService(self.memory, self.authorization, self.audit)
        self.artifacts = ArtifactService(
            self.workspace, self.authorization, self.revisions, audit=self.audit
        )
        self.capture = MeetingCaptureService(
            self.artifacts, self.memory, self.authorization, self.audit
        )
        self.room_id: str | None = None
        self.meeting_id: str | None = None
        self.update_channel = UPDATE_CHANNEL
        if not self.workspace.store.local_work_allowed():
            raise StaticMockError("local work must remain available on every platform")

    @property
    def capabilities(self) -> PlatformCapabilities:
        return capabilities_for(self.platform)

    @property
    def principal(self) -> Principal:
        return self.identity.principal(GOLDEN_ACTOR_ID)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()

    def identity_snapshot(self) -> PlatformIdentity:
        document = self.editor.document()
        laid_out = self.layout.layout(document)
        return PlatformIdentity(
            platform=self.platform,
            project_id=GOLDEN_PROJECT_ID,
            document_id=document.id,
            revision_id=self.revisions.canon_head_id(),
            branch_id=GOLDEN_BRANCH_ID,
            layout_hash=laid_out.layout_hash,
            layout_engine_version=LAYOUT_ENGINE_VERSION,
        )

    def is_mobile(self) -> bool:
        return self.platform in MOBILE_PLATFORMS

    def limitations(self) -> tuple[str, ...]:
        return self.capabilities.limitations

    def accessibility(self) -> AccessibilityBudget:
        return AccessibilityBudget(
            min_touch_target_pt=MIN_TOUCH_TARGET_PT,
            annotation_budget_seconds=ANNOTATION_BUDGET_SECONDS,
            large_target=self.is_mobile() or True,
        )

    def deep_link(self) -> str:
        snap = self.identity_snapshot()
        return (
            f"{DEEP_LINK_SCHEME}://project/{snap.project_id}/revision/{snap.revision_id}"
            f"?platform={self.platform.value}"
        )

    def parse_deep_link(self, url: str) -> PlatformIdentity:
        parsed = urlparse(url)
        if parsed.scheme != DEEP_LINK_SCHEME:
            raise DeepLinkError("unsupported deep link scheme")
        parts = [item for item in parsed.path.split("/") if item]
        if parsed.netloc == "project":
            parts = ["project", *parts]
        if len(parts) < 4 or parts[0] != "project" or parts[2] != "revision":
            raise DeepLinkError("deep link must target project and revision")
        project_id, revision_id = parts[1], parts[3]
        snap = self.identity_snapshot()
        if project_id != snap.project_id or revision_id != snap.revision_id:
            raise DeepLinkError("deep link project does not match the golden identity")
        query = parse_qs(parsed.query)
        platform = (query.get("platform") or [self.platform.value])[0]
        if platform != self.platform.value:
            raise DeepLinkError("deep link platform does not match this host")
        return snap

    def light_edit(self, text: str) -> str:
        ack = self.editor.update_text(GOLDEN_ACTION_ID, text)
        return ack.state.value if hasattr(ack, "state") else "saved"

    def long_form_checkpoint(self, name: str) -> str:
        if self.is_mobile():
            raise LongFormUnavailableError(
                "full long-form authoring is not on iPhone/Android yet; "
                + self.limitations()[0]
            )
        marker = self.editor.checkpoint(name)
        return str(getattr(marker, "id", name))

    def annotate(self, text: str) -> AnnotationResult:
        started = time.perf_counter()
        ack = self.editor.add_note(block_id=GOLDEN_ACTION_ID, text=text)
        del ack
        latency = time.perf_counter() - started
        note_id = self.editor.document().notes[-1].id
        return AnnotationResult(
            note_id=note_id,
            latency_seconds=latency,
            within_budget=latency <= ANNOTATION_BUDGET_SECONDS,
            target_pt=MIN_TOUCH_TARGET_PT,
        )

    def cards(self) -> tuple[SceneCard, ...]:
        return self.editor.cards()

    def references(self) -> tuple[str, ...]:
        return tuple(str(note.text) for note in self.editor.document().notes)

    def ensure_room(self) -> str:
        if self.room_id:
            return self.room_id
        session = self.rooms.start_room(
            project_id=GOLDEN_PROJECT_ID,
            branch_id=GOLDEN_BRANCH_ID,
            revision_id=self.revisions.canon_head_id(),
            principal=self.principal,
            acl_epoch=self.epoch,
            kind=RoomKind.SOLO,
            team_mode=RoomTeamMode.WRITER,
        )
        self.room_id = session.id
        return session.id

    def add_board_card(self, text: str) -> str:
        room_id = self.ensure_room()
        card = self.rooms.add_card(
            room_id,
            text=text,
            principal=self.principal,
            acl_epoch=self.epoch,
        )
        return card.id

    def begin_capture(self) -> str:
        if not self.capabilities.capture:
            raise CaptureConsentError("on-set capture is a mobile host job")
        meeting = self.capture.begin_session(
            project_id=GOLDEN_PROJECT_ID,
            branch_id=GOLDEN_BRANCH_ID,
            revision_id=self.revisions.canon_head_id(),
            principal=self.principal,
            acl_epoch=self.epoch,
            room_id=self.ensure_room(),
        )
        self.meeting_id = meeting.id
        if meeting.consent_state is not ConsentState.PENDING:
            raise CaptureConsentError("capture must start consent-first")
        return meeting.id

    def grant_capture_consent(self) -> str:
        if not self.meeting_id:
            raise CaptureConsentError("no capture session")
        updated = self.capture.grant_consent(
            self.meeting_id,
            principal=self.principal,
            acl_epoch=self.epoch,
        )
        return updated.consent_state.value

    def set_outage(self, name: str, enabled: bool) -> None:
        self.workspace.set_outage(name, enabled)
        if name == "connectivity_offline":
            self.editor.set_airplane(enabled)

    def flush_sync(self) -> list[str]:
        try:
            return self.sync.flush_outbox()
        except SyncUploadBlockedError:
            raise

    def reconnect(self) -> dict[str, object]:
        return self.sync.reconnect()

    def close(self) -> None:
        self.workspace.close()


def open_platform(
    platform: PlatformId | str,
    home: Path,
    *,
    origin: str = WEB_DEFAULT_ORIGIN,
    resume: bool = False,
) -> PlatformApp:
    parsed = platform if isinstance(platform, PlatformId) else PlatformId(platform)
    return PlatformApp(parsed, home, origin=origin, resume=resume)


def resume_platform(
    platform: PlatformId | str,
    home: Path,
    *,
    origin: str = WEB_DEFAULT_ORIGIN,
) -> PlatformApp:
    app = open_platform(platform, home, origin=origin, resume=True)
    if app.editor.document().id != GOLDEN_DOCUMENT_ID:
        raise StaticMockError("resumed workspace lost golden document identity")
    return app
