"""Preview-gated production correspondence over generic artifacts."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from movie_muse.artifacts.api import (
    ArtifactClassification,
    ArtifactService,
    ArtifactTemplateNotFoundError,
    ArtifactType,
    DeliveryRecord,
    RenderPurpose,
)
from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.correspondence.errors import (
    DraftNotFoundError,
    PreviewRequiredError,
    SendNotAuthorizedError,
)
from movie_muse.correspondence.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.correspondence.types import MessageDraft, MessagePreview, SendResult
from movie_muse.identity.api import Principal, PrincipalKind
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import ArtifactStatus, new_ulid

TEMPLATE_ID = "tmpl_correspondence_message"
TEMPLATE_VERSION = "1"
RENDERER_VERSION = "json/1"
TEMPLATE_BODY = "TO: {recipients}\nSUBJECT: {subject}\n\n{body}\n"


class CorrespondenceService:
    """Draft, preview, approve, and locally record message delivery. No implicit sends."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        artifacts: ArtifactService,
        revisions: RevisionService,
        *,
        live_channel_configured: bool = False,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.artifacts = artifacts
        self.revisions = revisions
        self.live_channel_configured = live_channel_configured
        self.clock = clock

    def draft_message(
        self,
        *,
        project_id: str,
        recipients: Sequence[str],
        subject: str,
        body: str,
        principal: Principal,
        acl_epoch: int,
        channel: str = "email",
        title: str | None = None,
    ) -> MessageDraft:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        if not recipients or not subject.strip() or not body.strip():
            raise PreviewRequiredError("drafts require recipients, subject, and body")
        self._ensure_template(project_id, principal, acl_epoch)
        artifact = self.artifacts.create_artifact(
            project_id=project_id,
            artifact_type=ArtifactType.DOCUMENT,
            title=title or subject,
            principal=principal,
            acl_epoch=acl_epoch,
        )
        version = self.artifacts.create_version(
            artifact.id,
            inputs={
                "recipients": ",".join(recipients),
                "subject": subject,
                "body": body,
                "channel": channel,
            },
            source_revision_id=self.revisions.canon_head_id(),
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            renderer_version=RENDERER_VERSION,
            classification=ArtifactClassification.RESTRICTED,
            principal=principal,
            acl_epoch=acl_epoch,
        )
        draft = MessageDraft(
            id=f"msg_{new_ulid()}",
            project_id=project_id,
            artifact_id=artifact.id,
            artifact_version_id=version.version.id,
            channel=channel,
            recipients=tuple(str(item) for item in recipients),
            subject=subject,
            body=body,
            created_at=self.clock(),
            created_by_actor_id=principal.actor_id,
        )
        stored = self._put_draft(draft)
        self._audit(principal, acl_epoch, "correspondence.draft", stored.id, channel)
        return stored

    def preview(
        self,
        draft_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> MessagePreview:
        draft = self._load(draft_id)
        self._require(principal, Action.READ, draft.project_id, acl_epoch)
        rendered = self.artifacts.render_version(
            draft.artifact_version_id,
            principal=principal,
            acl_epoch=acl_epoch,
            purpose=RenderPurpose.PREVIEW,
        )
        content = rendered.content.decode("utf-8")
        updated = MessageDraft(
            id=draft.id,
            project_id=draft.project_id,
            artifact_id=draft.artifact_id,
            artifact_version_id=draft.artifact_version_id,
            channel=draft.channel,
            recipients=draft.recipients,
            subject=draft.subject,
            body=draft.body,
            created_at=draft.created_at,
            created_by_actor_id=draft.created_by_actor_id,
            previewed=True,
            approved=draft.approved,
        )
        self._put_draft(updated)
        preview = MessagePreview(
            draft_id=draft.id,
            recipients=draft.recipients,
            subject=draft.subject,
            body=draft.body,
            content=content,
            render_id=rendered.render.id,
            checksum=rendered.render.checksum,
            channel=draft.channel,
        )
        self._audit(principal, acl_epoch, "correspondence.preview", draft.id, draft.channel)
        return preview

    def approve(
        self,
        draft_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> MessageDraft:
        if principal.kind is not PrincipalKind.HUMAN:
            raise SendNotAuthorizedError("only a human principal may approve correspondence")
        draft = self._load(draft_id)
        self._require(principal, Action.ACCEPT, draft.project_id, acl_epoch)
        if not draft.previewed:
            raise PreviewRequiredError("approve requires a preview of recipients and content")
        self.artifacts.transition_review(
            draft.artifact_version_id,
            ArtifactStatus.IN_REVIEW,
            principal=principal,
            acl_epoch=acl_epoch,
        )
        self.artifacts.transition_review(
            draft.artifact_version_id,
            ArtifactStatus.APPROVED,
            principal=principal,
            acl_epoch=acl_epoch,
        )
        updated = MessageDraft(
            id=draft.id,
            project_id=draft.project_id,
            artifact_id=draft.artifact_id,
            artifact_version_id=draft.artifact_version_id,
            channel=draft.channel,
            recipients=draft.recipients,
            subject=draft.subject,
            body=draft.body,
            created_at=draft.created_at,
            created_by_actor_id=draft.created_by_actor_id,
            previewed=True,
            approved=True,
        )
        stored = self._put_draft(updated)
        self._audit(principal, acl_epoch, "correspondence.approve", stored.id, stored.channel)
        return stored

    def send(
        self,
        draft_id: str,
        *,
        preview: MessagePreview,
        confirm: bool,
        principal: Principal,
        acl_epoch: int,
    ) -> SendResult:
        draft = self._load(draft_id)
        self._require(principal, Action.EXPORT, draft.project_id, acl_epoch)
        if not confirm:
            raise SendNotAuthorizedError("send requires explicit confirm=True after preview")
        if preview.draft_id != draft.id:
            raise PreviewRequiredError("preview does not match the draft")
        if tuple(preview.recipients) != draft.recipients or preview.subject != draft.subject:
            raise PreviewRequiredError("preview recipients/subject do not match the draft")
        if not draft.previewed or not draft.approved:
            raise PreviewRequiredError("send requires previewed and approved correspondence")
        deliveries: list[DeliveryRecord] = []
        for recipient in draft.recipients:
            deliveries.append(
                self.artifacts.deliver(
                    draft.artifact_version_id,
                    preview_render_id=preview.render_id,
                    preview_checksum=preview.checksum,
                    channel=draft.channel,
                    recipient=recipient,
                    confirm=True,
                    principal=principal,
                    acl_epoch=acl_epoch,
                )
            )
        delivery = deliveries[-1]
        if delivery.network_sent:
            raise SendNotAuthorizedError("live network send is not enabled for this channel")
        self._audit(principal, acl_epoch, "correspondence.send", draft.id, "local_record")
        return SendResult(draft=draft, delivery=delivery, network_sent=False)

    def get_draft(
        self, draft_id: str, *, principal: Principal, acl_epoch: int
    ) -> MessageDraft:
        draft = self._load(draft_id)
        self._require(principal, Action.READ, draft.project_id, acl_epoch)
        return draft

    def _ensure_template(self, project_id: str, principal: Principal, acl_epoch: int) -> None:
        try:
            self.artifacts.get_template(
                TEMPLATE_ID,
                TEMPLATE_VERSION,
                principal=principal,
                acl_epoch=acl_epoch,
            )
        except ArtifactTemplateNotFoundError:
            self.artifacts.register_template(
                project_id=project_id,
                template_id=TEMPLATE_ID,
                version=TEMPLATE_VERSION,
                renderer_version=RENDERER_VERSION,
                body=TEMPLATE_BODY,
                principal=principal,
                acl_epoch=acl_epoch,
            )

    def _load(self, draft_id: str) -> MessageDraft:
        index = load_index(self.workspace)
        digest = dict(index.get("draft_digests", {})).get(draft_id)
        if digest is None:
            raise DraftNotFoundError(f"draft {draft_id} is not in the index")
        return MessageDraft.from_dict(load_payload(self.workspace, str(digest)))

    def _put_draft(self, draft: MessageDraft) -> MessageDraft:
        def persist(index: dict[str, Any]) -> MessageDraft:
            digest = put_payload(self.workspace, draft.to_dict())
            ids = list(index.get("draft_ids", []))
            if draft.id not in ids:
                ids.append(draft.id)
            index["draft_ids"] = ids
            digests = dict(index.get("draft_digests", {}))
            digests[draft.id] = digest
            index["draft_digests"] = digests
            by_project = dict(index.get("by_project", {}))
            project_ids = list(by_project.get(draft.project_id, []))
            if draft.id not in project_ids:
                project_ids.append(draft.id)
            by_project[draft.project_id] = project_ids
            index["by_project"] = by_project
            return draft

        return mutate_index(self.workspace, persist)

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
            object_kind="correspondence",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
