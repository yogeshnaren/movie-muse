"""Permissioned, local-first implementation of the generic artifact lifecycle."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from movie_muse.artifacts.errors import (
    ArtifactDeliveryError,
    ArtifactImmutableError,
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    ArtifactReviewError,
    ArtifactTemplateNotFoundError,
    ArtifactTypeError,
    ArtifactVersionNotFoundError,
)
from movie_muse.artifacts.index import (
    clone_index,
    commit_index,
    load_index,
    load_json_blob,
    put_json_blob,
)
from movie_muse.artifacts.types import (
    ArtifactClassification,
    ArtifactComparison,
    ArtifactLink,
    ArtifactRender,
    ArtifactTemplate,
    ArtifactType,
    ArtifactVersionView,
    DeliveryRecord,
    RenderPurpose,
    RenderResult,
    ReviewRecord,
    StoredArtifactVersion,
)
from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import (
    Action,
    AuthorizationService,
    ResourceKind,
)
from movie_muse.identity.api import Principal, PrincipalKind
from movie_muse.persistence.api import LocalWorkspace, digest_payload, utc_now
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import Artifact, ArtifactStatus, ArtifactVersion, new_id, new_ulid

SUPPORTED_ARTIFACT_TYPES = frozenset(item.value for item in ArtifactType)
REVIEW_TRANSITIONS: dict[ArtifactStatus, frozenset[ArtifactStatus]] = {
    ArtifactStatus.DRAFT: frozenset({ArtifactStatus.IN_REVIEW}),
    ArtifactStatus.IN_REVIEW: frozenset({ArtifactStatus.APPROVED, ArtifactStatus.ARCHIVED}),
    ArtifactStatus.APPROVED: frozenset({ArtifactStatus.ARCHIVED}),
    ArtifactStatus.ARCHIVED: frozenset(),
}


class ArtifactService:
    """One content-addressed store and lifecycle for every generic artifact type."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        revisions: RevisionService,
        audit: AuditLog | None = None,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.revisions = revisions
        self.audit = audit or AuditLog(workspace)

    def create_artifact(
        self,
        *,
        project_id: str,
        artifact_type: ArtifactType | str,
        title: str,
        principal: Principal,
        acl_epoch: int,
    ) -> Artifact:
        parsed_type = self._parse_artifact_type(artifact_type)
        self.authorization.require(
            principal,
            Action.PROPOSE,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )
        artifact = Artifact(
            id=new_id("artifact"),
            project_id=project_id,
            artifact_type=parsed_type.value,
            title=title,
            created_at=utc_now(),
        )
        index = clone_index(load_index(self.workspace))
        digest = put_json_blob(self.workspace, artifact.to_dict())
        index["artifact_ids"] = [*index["artifact_ids"], artifact.id]
        index["artifact_digests"][artifact.id] = digest
        index["artifact_versions"][artifact.id] = []
        commit_index(self.workspace, index)
        self.authorization.declare_artifact(project_id=project_id, artifact_id=artifact.id)
        return artifact

    def get_artifact(
        self, artifact_id: str, *, principal: Principal, acl_epoch: int
    ) -> Artifact:
        artifact = self._artifact(artifact_id)
        self._require_artifact(principal, Action.READ, artifact, acl_epoch)
        return artifact

    def list_artifacts(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[Artifact, ...]:
        self.authorization.require(
            principal,
            Action.READ,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )
        index = load_index(self.workspace)
        return tuple(
            artifact
            for artifact_id in index["artifact_ids"]
            if (artifact := self._artifact(str(artifact_id))).project_id == project_id
        )

    def register_template(
        self,
        *,
        project_id: str,
        version: str,
        renderer_version: str,
        body: str,
        principal: Principal,
        acl_epoch: int,
        template_id: str | None = None,
    ) -> ArtifactTemplate:
        self.authorization.require(
            principal,
            Action.PROPOSE,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )
        template = ArtifactTemplate(
            id=template_id or self._local_id("tmpl"),
            project_id=project_id,
            version=version,
            renderer_version=renderer_version,
            body=body,
            creator_actor_id=principal.actor_id,
            created_at=utc_now(),
        )
        key = self._template_key(template.id, template.version)
        index = clone_index(load_index(self.workspace))
        if key in index["template_digests"]:
            raise ArtifactImmutableError(f"template version already exists: {key}")
        digest = put_json_blob(self.workspace, template.to_dict())
        index["template_keys"] = [*index["template_keys"], key]
        index["template_digests"][key] = digest
        commit_index(self.workspace, index)
        return template

    def get_template(
        self,
        template_id: str,
        template_version: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> ArtifactTemplate:
        template = self._template(template_id, template_version)
        self.authorization.require(
            principal,
            Action.READ,
            self.authorization.resource_for_project(template.project_id),
            acl_epoch=acl_epoch,
        )
        return template

    def create_version(
        self,
        artifact_id: str,
        *,
        inputs: Mapping[str, Any],
        source_revision_id: str,
        template_id: str,
        template_version: str,
        renderer_version: str,
        classification: ArtifactClassification | str,
        principal: Principal,
        acl_epoch: int,
        evidence_bundle_ids: tuple[str, ...] = (),
        rights_record_ids: tuple[str, ...] = (),
        purpose: RenderPurpose = RenderPurpose.GENERATION,
    ) -> ArtifactVersionView:
        artifact = self._artifact(artifact_id)
        self._require_artifact(principal, Action.PROPOSE, artifact, acl_epoch)
        template = self._template(template_id, template_version)
        if template.project_id != artifact.project_id:
            raise ArtifactTemplateNotFoundError("template belongs to another project")
        if renderer_version != template.renderer_version:
            raise ArtifactTemplateNotFoundError("template renderer version does not match")
        source_payload = self._source_payload(source_revision_id, artifact.project_id)
        inputs_json, canonical_inputs = self._canonical_inputs(inputs)
        content, checksum = self._render_bytes(
            artifact=artifact,
            template=template,
            renderer_version=renderer_version,
            inputs=canonical_inputs,
            source_revision_id=source_revision_id,
            source_payload=source_payload,
        )
        version_id = new_id("artifact_version")
        render = ArtifactRender(
            id=self._local_id("rnd"),
            artifact_version_id=version_id,
            source_revision_id=source_revision_id,
            template_id=template.id,
            template_version=template.version,
            renderer_version=renderer_version,
            checksum=checksum,
            blob_digest=self.workspace.store.put_blob(content, expected_digest=checksum),
            purpose=purpose,
            actor_id=principal.actor_id,
            created_at=utc_now(),
        )
        version = ArtifactVersion(
            id=version_id,
            artifact_id=artifact.id,
            source_revision_id=source_revision_id,
            template_id=template.id,
            template_version=template.version,
            renderer_version=renderer_version,
            checksum=checksum,
            created_at=utc_now(),
            creator_actor_id=principal.actor_id,
            status=ArtifactStatus.DRAFT,
            evidence_bundle_ids=tuple(evidence_bundle_ids),
            rights_record_ids=tuple(rights_record_ids),
        )
        stored = StoredArtifactVersion(
            version=version,
            inputs_json=inputs_json,
            classification=(
                classification
                if isinstance(classification, ArtifactClassification)
                else ArtifactClassification(str(classification))
            ),
            editor_actor_id=principal.actor_id,
            render_id=render.id,
        )
        link = self._new_link(
            artifact=artifact,
            artifact_version_id=version.id,
            source_revision_id=source_revision_id,
            relation="generated_from",
            actor_id=principal.actor_id,
        )
        index = clone_index(load_index(self.workspace))
        self._persist_version(index, stored, render, link)
        commit_index(self.workspace, index)
        return ArtifactVersionView(record=stored, status=ArtifactStatus.DRAFT)

    def regenerate(
        self,
        artifact_version_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        source_revision_id: str | None = None,
    ) -> ArtifactVersionView:
        prior = self._stored_version(artifact_version_id)
        return self.create_version(
            prior.version.artifact_id,
            inputs=json.loads(prior.inputs_json),
            source_revision_id=source_revision_id or prior.version.source_revision_id,
            template_id=prior.version.template_id,
            template_version=prior.version.template_version,
            renderer_version=prior.version.renderer_version,
            classification=prior.classification,
            principal=principal,
            acl_epoch=acl_epoch,
            evidence_bundle_ids=prior.version.evidence_bundle_ids,
            rights_record_ids=prior.version.rights_record_ids,
            purpose=RenderPurpose.REGENERATION,
        )

    def get_version(
        self, artifact_version_id: str, *, principal: Principal, acl_epoch: int
    ) -> ArtifactVersionView:
        stored = self._stored_version(artifact_version_id)
        artifact = self._artifact(stored.version.artifact_id)
        self._require_artifact(principal, Action.READ, artifact, acl_epoch)
        return self._version_view(stored)

    def list_versions(
        self, artifact_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[ArtifactVersionView, ...]:
        artifact = self._artifact(artifact_id)
        self._require_artifact(principal, Action.READ, artifact, acl_epoch)
        index = load_index(self.workspace)
        return tuple(
            self._version_view(self._stored_version(str(version_id)))
            for version_id in index["artifact_versions"].get(artifact_id, [])
        )

    def render_version(
        self,
        artifact_version_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        purpose: RenderPurpose = RenderPurpose.GENERATION,
    ) -> RenderResult:
        stored = self._stored_version(artifact_version_id)
        artifact = self._artifact(stored.version.artifact_id)
        self._require_artifact(principal, Action.READ, artifact, acl_epoch)
        template = self._template(stored.version.template_id, stored.version.template_version)
        source_payload = self._source_payload(
            stored.version.source_revision_id, artifact.project_id
        )
        content, checksum = self._render_bytes(
            artifact=artifact,
            template=template,
            renderer_version=stored.version.renderer_version,
            inputs=json.loads(stored.inputs_json),
            source_revision_id=stored.version.source_revision_id,
            source_payload=source_payload,
        )
        if checksum != stored.version.checksum:
            raise ArtifactIntegrityError("re-render checksum does not match immutable version")
        render = ArtifactRender(
            id=self._local_id("rnd"),
            artifact_version_id=stored.version.id,
            source_revision_id=stored.version.source_revision_id,
            template_id=stored.version.template_id,
            template_version=stored.version.template_version,
            renderer_version=stored.version.renderer_version,
            checksum=checksum,
            blob_digest=self.workspace.store.put_blob(content, expected_digest=checksum),
            purpose=purpose,
            actor_id=principal.actor_id,
            created_at=utc_now(),
        )
        index = clone_index(load_index(self.workspace))
        self._persist_render(index, render)
        commit_index(self.workspace, index)
        return RenderResult(render=render, content=content)

    def preview(
        self, artifact_version_id: str, *, principal: Principal, acl_epoch: int
    ) -> RenderResult:
        return self.render_version(
            artifact_version_id,
            principal=principal,
            acl_epoch=acl_epoch,
            purpose=RenderPurpose.PREVIEW,
        )

    def compare(
        self,
        left_version_id: str,
        right_version_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> ArtifactComparison:
        left = self.get_version(left_version_id, principal=principal, acl_epoch=acl_epoch)
        right = self.get_version(right_version_id, principal=principal, acl_epoch=acl_epoch)
        if left.version.artifact_id != right.version.artifact_id:
            raise ArtifactReviewError("versions from different artifacts cannot be compared")
        left_inputs = dict(left.record.inputs)
        right_inputs = dict(right.record.inputs)
        changed_keys = tuple(
            sorted(
                key
                for key in set(left_inputs) | set(right_inputs)
                if left_inputs.get(key) != right_inputs.get(key)
            )
        )
        return ArtifactComparison(
            left_version_id=left.version.id,
            right_version_id=right.version.id,
            checksum_changed=left.version.checksum != right.version.checksum,
            status_changed=left.status is not right.status,
            source_revision_changed=(
                left.version.source_revision_id != right.version.source_revision_id
            ),
            inputs_changed=bool(changed_keys),
            changed_input_keys=changed_keys,
        )

    def transition_review(
        self,
        artifact_version_id: str,
        to_status: ArtifactStatus | str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> ArtifactVersionView:
        stored = self._stored_version(artifact_version_id)
        artifact = self._artifact(stored.version.artifact_id)
        current = self._version_view(stored)
        target = (
            to_status
            if isinstance(to_status, ArtifactStatus)
            else ArtifactStatus(str(to_status))
        )
        if target not in REVIEW_TRANSITIONS[current.status]:
            raise ArtifactReviewError(
                f"invalid review transition: {current.status.value} -> {target.value}"
            )
        action = Action.PROPOSE if target is ArtifactStatus.IN_REVIEW else Action.ACCEPT
        self._require_artifact(principal, action, artifact, acl_epoch)
        if action is Action.ACCEPT and principal.kind is not PrincipalKind.HUMAN:
            raise ArtifactReviewError("approval and archive require an authorized human")
        review = ReviewRecord(
            id=self._local_id("rvw"),
            artifact_version_id=artifact_version_id,
            from_status=current.status,
            to_status=target,
            actor_id=principal.actor_id,
            created_at=utc_now(),
        )
        index = clone_index(load_index(self.workspace))
        digest = put_json_blob(self.workspace, review.to_dict())
        index["review_ids"] = [*index["review_ids"], review.id]
        index["review_digests"][review.id] = digest
        index["version_reviews"][artifact_version_id] = [
            *index["version_reviews"].get(artifact_version_id, []),
            review.id,
        ]
        commit_index(self.workspace, index)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=f"artifact_review_{target.value}",
            object_kind="artifact_version",
            object_id=artifact_version_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason="explicit_human_review" if action is Action.ACCEPT else "submitted_for_review",
            before_revision_id=stored.version.source_revision_id,
            after_revision_id=stored.version.source_revision_id,
        )
        return ArtifactVersionView(record=stored, status=target, latest_review=review)

    def link_to_revision(
        self,
        artifact_version_id: str,
        source_revision_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        relation: str = "references",
    ) -> ArtifactLink:
        stored = self._stored_version(artifact_version_id)
        artifact = self._artifact(stored.version.artifact_id)
        self._require_artifact(principal, Action.PROPOSE, artifact, acl_epoch)
        self._source_payload(source_revision_id, artifact.project_id)
        link = self._new_link(
            artifact=artifact,
            artifact_version_id=artifact_version_id,
            source_revision_id=source_revision_id,
            relation=relation,
            actor_id=principal.actor_id,
        )
        index = clone_index(load_index(self.workspace))
        self._persist_link(index, link)
        commit_index(self.workspace, index)
        return link

    def list_links(
        self, artifact_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[ArtifactLink, ...]:
        artifact = self._artifact(artifact_id)
        self._require_artifact(principal, Action.READ, artifact, acl_epoch)
        index = load_index(self.workspace)
        links = (
            ArtifactLink.from_dict(
                load_json_blob(self.workspace, str(index["link_digests"][link_id]))
            )
            for link_id in index["link_ids"]
        )
        return tuple(link for link in links if link.artifact_id == artifact_id)

    def export_version(
        self,
        artifact_version_id: str,
        destination: Path,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> Path:
        stored = self._stored_version(artifact_version_id)
        artifact = self._artifact(stored.version.artifact_id)
        self._require_artifact(principal, Action.EXPORT, artifact, acl_epoch)
        result = self.render_version(
            artifact_version_id,
            principal=principal,
            acl_epoch=acl_epoch,
            purpose=RenderPurpose.EXPORT,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(result.content)
        return destination

    def deliver(
        self,
        artifact_version_id: str,
        *,
        preview_render_id: str,
        preview_checksum: str,
        channel: str,
        recipient: str,
        confirm: bool,
        principal: Principal,
        acl_epoch: int,
    ) -> DeliveryRecord:
        stored = self._stored_version(artifact_version_id)
        artifact = self._artifact(stored.version.artifact_id)
        self._require_artifact(principal, Action.EXPORT, artifact, acl_epoch)
        if not confirm:
            raise ArtifactDeliveryError("delivery requires explicit confirm=True")
        preview = self._render(preview_render_id)
        if (
            preview.purpose is not RenderPurpose.PREVIEW
            or preview.artifact_version_id != artifact_version_id
            or preview.checksum != preview_checksum
            or preview.checksum != stored.version.checksum
        ):
            raise ArtifactDeliveryError("delivery preview id/checksum does not match version")
        delivery = DeliveryRecord(
            id=self._local_id("dlv"),
            artifact_version_id=artifact_version_id,
            preview_render_id=preview_render_id,
            preview_checksum=preview_checksum,
            channel=channel,
            recipient=recipient,
            actor_id=principal.actor_id,
            created_at=utc_now(),
            network_sent=False,
        )
        index = clone_index(load_index(self.workspace))
        digest = put_json_blob(self.workspace, delivery.to_dict())
        index["delivery_ids"] = [*index["delivery_ids"], delivery.id]
        index["delivery_digests"][delivery.id] = digest
        commit_index(self.workspace, index)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="artifact_delivery_confirmed",
            object_kind="artifact_version",
            object_id=artifact_version_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=f"preview_confirmed:{preview_render_id}",
            before_revision_id=stored.version.source_revision_id,
            after_revision_id=stored.version.source_revision_id,
        )
        return delivery

    def list_deliveries(
        self, artifact_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[DeliveryRecord, ...]:
        artifact = self._artifact(artifact_id)
        self._require_artifact(principal, Action.READ, artifact, acl_epoch)
        version_ids = {
            view.version.id
            for view in self.list_versions(
                artifact_id, principal=principal, acl_epoch=acl_epoch
            )
        }
        index = load_index(self.workspace)
        records = (
            DeliveryRecord.from_dict(
                load_json_blob(self.workspace, str(index["delivery_digests"][record_id]))
            )
            for record_id in index["delivery_ids"]
        )
        return tuple(record for record in records if record.artifact_version_id in version_ids)

    def investor_listing(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[ArtifactVersionView, ...]:
        self.authorization.require(
            principal,
            Action.READ,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )
        approved: list[ArtifactVersionView] = []
        for artifact in self.list_artifacts(
            project_id, principal=principal, acl_epoch=acl_epoch
        ):
            approved.extend(
                view
                for view in self.list_versions(
                    artifact.id, principal=principal, acl_epoch=acl_epoch
                )
                if view.status is ArtifactStatus.APPROVED
            )
        return tuple(approved)

    def update_version(
        self,
        artifact_version_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        **_changes: object,
    ) -> None:
        stored = self._stored_version(artifact_version_id)
        artifact = self._artifact(stored.version.artifact_id)
        self._require_artifact(principal, Action.PROPOSE, artifact, acl_epoch)
        raise ArtifactImmutableError(f"artifact versions cannot be updated: {artifact_version_id}")

    def delete_version(
        self,
        artifact_version_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> None:
        stored = self._stored_version(artifact_version_id)
        artifact = self._artifact(stored.version.artifact_id)
        self._require_artifact(principal, Action.PROPOSE, artifact, acl_epoch)
        raise ArtifactImmutableError(f"artifact versions cannot be deleted: {artifact_version_id}")

    def _artifact(self, artifact_id: str) -> Artifact:
        index = load_index(self.workspace)
        digest = index["artifact_digests"].get(artifact_id)
        if digest is None:
            raise ArtifactNotFoundError(f"unknown artifact: {artifact_id}")
        return Artifact.from_dict(load_json_blob(self.workspace, str(digest)))

    def _template(self, template_id: str, template_version: str) -> ArtifactTemplate:
        index = load_index(self.workspace)
        key = self._template_key(template_id, template_version)
        digest = index["template_digests"].get(key)
        if digest is None:
            raise ArtifactTemplateNotFoundError(f"unknown template version: {key}")
        return ArtifactTemplate.from_dict(load_json_blob(self.workspace, str(digest)))

    def _stored_version(self, artifact_version_id: str) -> StoredArtifactVersion:
        index = load_index(self.workspace)
        digest = index["version_digests"].get(artifact_version_id)
        if digest is None:
            raise ArtifactVersionNotFoundError(
                f"unknown artifact version: {artifact_version_id}"
            )
        stored = StoredArtifactVersion.from_dict(
            load_json_blob(self.workspace, str(digest))
        )
        render = self._render(stored.render_id)
        if (
            render.artifact_version_id != stored.version.id
            or render.checksum != stored.version.checksum
            or render.blob_digest != stored.version.checksum
        ):
            raise ArtifactIntegrityError("version render metadata does not match")
        content = self.workspace.store.get_blob(render.blob_digest)
        _payload, checksum = digest_payload(json.loads(content.decode("utf-8")))
        if checksum != stored.version.checksum:
            raise ArtifactIntegrityError("version content checksum does not match")
        return stored

    def _render(self, render_id: str) -> ArtifactRender:
        index = load_index(self.workspace)
        digest = index["render_digests"].get(render_id)
        if digest is None:
            raise ArtifactIntegrityError(f"unknown artifact render: {render_id}")
        return ArtifactRender.from_dict(load_json_blob(self.workspace, str(digest)))

    def _version_view(self, stored: StoredArtifactVersion) -> ArtifactVersionView:
        index = load_index(self.workspace)
        review_ids = index["version_reviews"].get(stored.version.id, [])
        if not review_ids:
            return ArtifactVersionView(record=stored, status=ArtifactStatus.DRAFT)
        review_id = str(review_ids[-1])
        review = ReviewRecord.from_dict(
            load_json_blob(self.workspace, str(index["review_digests"][review_id]))
        )
        return ArtifactVersionView(
            record=stored, status=review.to_status, latest_review=review
        )

    def _require_artifact(
        self,
        principal: Principal,
        action: Action,
        artifact: Artifact,
        acl_epoch: int,
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(
                artifact.project_id,
                kind=ResourceKind.ARTIFACT,
                resource_id=artifact.id,
            ),
            acl_epoch=acl_epoch,
        )

    def _source_payload(self, source_revision_id: str, project_id: str) -> dict[str, Any]:
        document = self.revisions.load_revision(source_revision_id)
        if document.project_id != project_id:
            raise ArtifactIntegrityError("source revision belongs to another project")
        payload = json.loads(self.revisions.revision_blob_bytes(source_revision_id).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ArtifactIntegrityError("source revision payload is not an object")
        return payload

    @staticmethod
    def _canonical_inputs(inputs: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        copied = _json_compatible(inputs)
        if not isinstance(copied, dict):
            raise ArtifactIntegrityError("artifact inputs must be an object")
        encoded, _digest = digest_payload(copied)
        decoded = json.loads(encoded.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ArtifactIntegrityError("artifact inputs must be an object")
        return encoded.decode("utf-8"), decoded

    @staticmethod
    def _render_bytes(
        *,
        artifact: Artifact,
        template: ArtifactTemplate,
        renderer_version: str,
        inputs: dict[str, Any],
        source_revision_id: str,
        source_payload: dict[str, Any],
    ) -> tuple[bytes, str]:
        return digest_payload(
            {
                "artifact_type": artifact.artifact_type,
                "format": "movie-muse-artifact-render/1.0",
                "inputs": inputs,
                "renderer_version": renderer_version,
                "source_revision": {
                    "id": source_revision_id,
                    "payload": source_payload,
                },
                "template": {
                    "body": template.body,
                    "id": template.id,
                    "version": template.version,
                },
            }
        )

    @staticmethod
    def _parse_artifact_type(artifact_type: ArtifactType | str) -> ArtifactType:
        try:
            return artifact_type if isinstance(artifact_type, ArtifactType) else ArtifactType(
                str(artifact_type)
            )
        except ValueError as exc:
            raise ArtifactTypeError(
                f"unsupported artifact type; expected one of {sorted(SUPPORTED_ARTIFACT_TYPES)}"
            ) from exc

    @staticmethod
    def _template_key(template_id: str, template_version: str) -> str:
        return f"{template_id}@{template_version}"

    @staticmethod
    def _local_id(prefix: str) -> str:
        return f"{prefix}_{new_ulid()}"

    @staticmethod
    def _new_link(
        *,
        artifact: Artifact,
        artifact_version_id: str,
        source_revision_id: str,
        relation: str,
        actor_id: str,
    ) -> ArtifactLink:
        return ArtifactLink(
            id=f"lnk_{new_ulid()}",
            artifact_id=artifact.id,
            artifact_version_id=artifact_version_id,
            source_revision_id=source_revision_id,
            relation=relation,
            actor_id=actor_id,
            created_at=utc_now(),
        )

    def _persist_version(
        self,
        index: dict[str, Any],
        stored: StoredArtifactVersion,
        render: ArtifactRender,
        link: ArtifactLink,
    ) -> None:
        version_id = stored.version.id
        if version_id in index["version_digests"]:
            raise ArtifactImmutableError(f"artifact version already exists: {version_id}")
        index["version_ids"] = [*index["version_ids"], version_id]
        index["version_digests"][version_id] = put_json_blob(
            self.workspace, stored.to_dict()
        )
        index["artifact_versions"][stored.version.artifact_id] = [
            *index["artifact_versions"].get(stored.version.artifact_id, []),
            version_id,
        ]
        index["version_reviews"][version_id] = []
        self._persist_render(index, render)
        self._persist_link(index, link)

    def _persist_render(self, index: dict[str, Any], render: ArtifactRender) -> None:
        index["render_ids"] = [*index["render_ids"], render.id]
        index["render_digests"][render.id] = put_json_blob(
            self.workspace, render.to_dict()
        )

    def _persist_link(self, index: dict[str, Any], link: ArtifactLink) -> None:
        index["link_ids"] = [*index["link_ids"], link.id]
        index["link_digests"][link.id] = put_json_blob(
            self.workspace, link.to_dict()
        )


def _json_compatible(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_compatible(item) for item in value]
    if value is None or isinstance(value, bool | int | float | str):
        return value
    raise ArtifactIntegrityError(
        f"artifact inputs must contain JSON values, got {type(value).__name__}"
    )
