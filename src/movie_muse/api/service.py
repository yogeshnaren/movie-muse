"""Versioned least-privilege Integration Mesh over local project state."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from movie_muse.api.errors import (
    CommitDeniedError,
    CompatibilityError,
    CredentialError,
    IdempotencyConflictError,
    MeshNotFoundError,
    RateLimitError,
    SourceOfTruthError,
)
from movie_muse.api.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.api.injection import assert_no_injection
from movie_muse.api.openapi import openapi_v1
from movie_muse.api.sdk import OpenFileFallback, ProductionReviewAdapter, example_client_flow
from movie_muse.api.types import (
    API_VERSION,
    FIELD_SOURCE_OF_TRUTH,
    RATE_LIMIT_DEFAULT,
    RATE_WINDOW_SECONDS,
    SUPPORTED_VERSIONS,
    TOKEN_PREFIX,
    CredentialStatus,
    IssuedToken,
    MeshCapability,
    ProjectStatus,
    SourceOfTruth,
    SyncRecord,
    ToolSide,
    VaultCredential,
)
from movie_muse.artifacts.api import ArtifactService
from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.identity.api import IdentityService, Principal, PrincipalKind
from movie_muse.persistence.api import LocalWorkspace, digest_payload
from movie_muse.proposals.api import (
    DirectCanonWriteError,
    ProposalEnvelope,
    ProposalOrigin,
    ProposalService,
)
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import ArtifactStatus, ChangeSet, new_ulid


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class IntegrationMeshService:
    """Least-privilege API over projects, revisions, proposals, artifacts, status."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        identity: IdentityService,
        audit: AuditLog,
        revisions: RevisionService,
        proposals: ProposalService,
        artifacts: ArtifactService,
        *,
        clock: Callable[[], datetime] | None = None,
        rate_limit: int = RATE_LIMIT_DEFAULT,
        rate_window_seconds: int = RATE_WINDOW_SECONDS,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.identity = identity
        self.audit = audit
        self.revisions = revisions
        self.proposals = proposals
        self.artifacts = artifacts
        self.clock = clock or (lambda: datetime.now(UTC))
        self.rate_limit = rate_limit
        self.rate_window_seconds = rate_window_seconds
        self.review_adapter = ProductionReviewAdapter()
        self.open_file = OpenFileFallback(artifacts)

    def assert_version(self, version: str) -> str:
        cleaned = version.strip()
        if cleaned not in SUPPORTED_VERSIONS:
            raise CompatibilityError(f"unsupported API version {version}; expected {API_VERSION}")
        return cleaned

    def source_of_truth(self, field: str) -> SourceOfTruth:
        owner = FIELD_SOURCE_OF_TRUTH.get(field)
        if owner is None:
            raise SourceOfTruthError(f"unknown field {field}")
        return owner

    def assert_field_writable(self, field: str, *, side: ToolSide) -> None:
        owner = self.source_of_truth(field)
        if owner is SourceOfTruth.EXTERNAL_SPECIALIST:
            raise SourceOfTruthError(
                f"{field} is owned by an external specialist; use that system or open-file fallback"
            )
        if side is ToolSide.COMMIT and owner is SourceOfTruth.MOVIE_MUSE:
            return
        if side is ToolSide.PROPOSE and owner is SourceOfTruth.MOVIE_MUSE:
            return
        if side is ToolSide.READ:
            return

    def ignore_unknown_fields(self, payload: Mapping[str, Any], known: Sequence[str]) -> dict[str, Any]:
        allowed = set(known)
        return {str(key): value for key, value in payload.items() if str(key) in allowed}

    def openapi(self) -> dict[str, Any]:
        return openapi_v1()

    def sdk_example(self) -> dict[str, str]:
        return example_client_flow()

    def get_project(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> dict[str, str]:
        self._meter(principal)
        self._require(principal, Action.READ, project_id, acl_epoch)
        head = self.revisions.replay_head()
        if head.project_id != project_id:
            raise MeshNotFoundError(f"project {project_id} is not the active workspace project")
        self._audit(principal, acl_epoch, "mesh.project.read", project_id, API_VERSION)
        return {
            "id": project_id,
            "title": head.title,
            "api_version": API_VERSION,
        }

    def get_revision_head(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> dict[str, str]:
        self._meter(principal)
        self._require(principal, Action.READ, project_id, acl_epoch)
        head_id = self.revisions.canon_head_id()
        self._audit(principal, acl_epoch, "mesh.revision.read", head_id, project_id)
        return {"project_id": project_id, "head_revision_id": head_id}

    def list_proposals(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[str, ...]:
        self._meter(principal)
        self._require(principal, Action.READ, project_id, acl_epoch)
        ids = tuple(
            item.id for item in self.revisions.list_proposals() if item.project_id == project_id
        )
        self._audit(principal, acl_epoch, "mesh.proposal.list", project_id, str(len(ids)))
        return ids

    def list_approved_artifacts(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[str, ...]:
        self._meter(principal)
        self._require(principal, Action.READ, project_id, acl_epoch)
        approved: list[str] = []
        for artifact in self.artifacts.list_artifacts(
            project_id, principal=principal, acl_epoch=acl_epoch
        ):
            for view in self.artifacts.list_versions(
                artifact.id, principal=principal, acl_epoch=acl_epoch
            ):
                if view.status is ArtifactStatus.APPROVED:
                    approved.append(view.version.id)
        self._audit(
            principal, acl_epoch, "mesh.artifact.list_approved", project_id, str(len(approved))
        )
        return tuple(approved)

    def status(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> ProjectStatus:
        self._meter(principal)
        self._require(principal, Action.READ, project_id, acl_epoch)
        head = self.revisions.replay_head()
        proposal_count = len(
            tuple(item.id for item in self.revisions.list_proposals() if item.project_id == project_id)
        )
        approved_count = 0
        for artifact in self.artifacts.list_artifacts(
            project_id, principal=principal, acl_epoch=acl_epoch
        ):
            for view in self.artifacts.list_versions(
                artifact.id, principal=principal, acl_epoch=acl_epoch
            ):
                if view.status is ArtifactStatus.APPROVED:
                    approved_count += 1
        stored = ProjectStatus(
            project_id=project_id,
            title=head.title,
            head_revision_id=self.revisions.canon_head_id(),
            api_version=API_VERSION,
            proposal_count=proposal_count,
            approved_artifact_count=approved_count,
        )
        self._audit(principal, acl_epoch, "mesh.status.read", project_id, stored.head_revision_id)
        return stored

    def propose(
        self,
        project_id: str,
        change_set: ChangeSet,
        *,
        principal: Principal,
        acl_epoch: int,
        intent: str,
        rationale_summary: str,
        provenance: str,
        idempotency_key: str | None = None,
        extra_payload: Mapping[str, Any] | None = None,
    ) -> ProposalEnvelope:
        self._meter(principal)
        self.assert_field_writable("proposals", side=ToolSide.PROPOSE)
        if extra_payload:
            self.ignore_unknown_fields(extra_payload, ("intent", "rationale_summary", "provenance"))
        assert_no_injection(intent, rationale_summary, provenance)
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        origin = (
            ProposalOrigin.AI
            if principal.kind is not PrincipalKind.HUMAN
            else ProposalOrigin.HUMAN
        )
        fingerprint = digest_payload(
            {
                "project_id": project_id,
                "change_set": change_set.to_dict(),
                "intent": intent,
                "rationale": rationale_summary,
            }
        )[1]
        if idempotency_key:
            existing = self._idempotent_get(idempotency_key, fingerprint)
            if existing is not None:
                return self.proposals.review(str(existing)).envelope
        envelope = self.proposals.submit(
            change_set,
            principal=principal,
            acl_epoch=acl_epoch,
            project_id=project_id,
            intent=intent,
            rationale_summary=rationale_summary,
            provenance=provenance,
            origin=origin,
        )
        if idempotency_key:
            self._idempotent_put(idempotency_key, fingerprint, envelope.proposal.id)
        self._audit(principal, acl_epoch, "mesh.proposal.propose", envelope.proposal.id, origin.value)
        return envelope

    def commit(
        self,
        proposal_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        field: str = "proposals",
    ) -> dict[str, str]:
        self._meter(principal)
        self.assert_field_writable(field, side=ToolSide.COMMIT)
        if principal.kind is not PrincipalKind.HUMAN:
            raise CommitDeniedError("integrations cannot commit canon or bypass creator approval")
        try:
            result = self.proposals.accept(
                proposal_id, principal=principal, acl_epoch=acl_epoch
            )
        except DirectCanonWriteError as exc:
            raise CommitDeniedError("integrations cannot commit canon or bypass creator approval") from exc
        self._audit(principal, acl_epoch, "mesh.proposal.commit", proposal_id, result.revision_id)
        return {"proposal_id": proposal_id, "revision_id": result.revision_id}

    def issue_token(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        scopes: Sequence[str],
        expires_at: str,
    ) -> IssuedToken:
        self._require(principal, Action.MANAGE_ACL, project_id, acl_epoch)
        token = f"{TOKEN_PREFIX}{new_ulid()}"
        credential = VaultCredential(
            id=f"vlt_{new_ulid()}",
            actor_id=principal.actor_id,
            project_id=project_id,
            scopes=tuple(str(item) for item in scopes),
            status=CredentialStatus.ACTIVE,
            token_digest=_token_digest(token),
            expires_at=expires_at,
            created_at=self._stamp(),
        )
        written = self._put_credential(credential)
        self._audit(principal, acl_epoch, "mesh.vault.issue", written.id, ",".join(written.scopes))
        return IssuedToken(credential=written, token=token)

    def authenticate_token(self, token: str) -> VaultCredential:
        digest = _token_digest(token.strip())
        index = load_index(self.workspace)
        credential_id = dict(index.get("token_digests", {})).get(digest)
        if credential_id is None:
            raise CredentialError("unknown or revoked mesh token")
        stored = self._load_credential(str(credential_id))
        if stored.status is not CredentialStatus.ACTIVE:
            raise CredentialError("mesh token is expired or revoked")
        if stored.expires_at < self._stamp():
            self._put_credential(
                VaultCredential(
                    id=stored.id,
                    actor_id=stored.actor_id,
                    project_id=stored.project_id,
                    scopes=stored.scopes,
                    status=CredentialStatus.EXPIRED,
                    token_digest=stored.token_digest,
                    expires_at=stored.expires_at,
                    created_at=stored.created_at,
                )
            )
            raise CredentialError("mesh token is expired or revoked")
        return stored

    def revoke_token(
        self, credential_id: str, *, principal: Principal, acl_epoch: int
    ) -> VaultCredential:
        stored = self._load_credential(credential_id)
        self._require(principal, Action.MANAGE_ACL, stored.project_id, acl_epoch)
        revoked = VaultCredential(
            id=stored.id,
            actor_id=stored.actor_id,
            project_id=stored.project_id,
            scopes=stored.scopes,
            status=CredentialStatus.REVOKED,
            token_digest=stored.token_digest,
            expires_at=stored.expires_at,
            created_at=stored.created_at,
        )
        written = self._put_credential(revoked)
        self._audit(principal, acl_epoch, "mesh.vault.revoke", written.id, written.status.value)
        return written

    def register_capability(
        self,
        *,
        name: str,
        side: ToolSide | str,
        scopes: Sequence[str],
        principal: Principal,
        acl_epoch: int,
        project_id: str,
    ) -> MeshCapability:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        parsed = side if isinstance(side, ToolSide) else ToolSide(str(side))
        item = MeshCapability(
            id=f"cap_{new_ulid()}",
            name=name.strip(),
            side=parsed,
            scopes=tuple(str(item) for item in scopes),
        )
        written = self._put_capability(item)
        self._audit(principal, acl_epoch, "mesh.capability.register", written.id, written.side.value)
        return written

    def list_capabilities(self) -> tuple[MeshCapability, ...]:
        index = load_index(self.workspace)
        ids = list(index.get("capability_ids", []))
        return tuple(self._load_capability(str(item_id)) for item_id in ids)

    def record_sync(
        self,
        project_id: str,
        *,
        capability_id: str,
        payload: Mapping[str, Any],
        source: str,
        principal: Principal,
        acl_epoch: int,
    ) -> SyncRecord:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        self._load_capability(capability_id)
        digest = digest_payload(dict(payload))[1]
        item = SyncRecord(
            id=f"syn_{new_ulid()}",
            project_id=project_id,
            capability_id=capability_id,
            payload_digest=digest,
            source=source.strip(),
            created_at=self._stamp(),
        )
        written = self._put_sync(item)
        self._audit(principal, acl_epoch, "mesh.sync.record", written.id, written.capability_id)
        return written

    def export_open_file(
        self,
        artifact_version_id: str,
        destination: Path,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> Path:
        self._meter(principal)
        path = self.open_file.export_approved(
            artifact_version_id,
            destination,
            principal=principal,
            acl_epoch=acl_epoch,
        )
        self._audit(principal, acl_epoch, "mesh.fallback.export", artifact_version_id, str(path))
        return path

    def specialist_push(
        self,
        artifact_version_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> str:
        self._meter(principal)
        self._require(principal, Action.EXPORT, self._active_project_id(), acl_epoch)
        return self.review_adapter.push_approved(
            artifact_version_id, principal=principal, acl_epoch=acl_epoch
        )

    def _active_project_id(self) -> str:
        return self.revisions.replay_head().project_id

    def _stamp(self) -> str:
        return self.clock().strftime("%Y-%m-%dT%H:%M:%SZ")

    def _meter(self, principal: Principal) -> None:
        now = self.clock()
        cutoff = now - timedelta(seconds=self.rate_window_seconds)

        def persist(index: dict[str, Any]) -> None:
            stamps = dict(index.get("rate_stamps", {}))
            series = [
                datetime.fromisoformat(item.replace("Z", "+00:00"))
                for item in list(stamps.get(principal.actor_id, []))
            ]
            kept = [item for item in series if item >= cutoff]
            if len(kept) >= self.rate_limit:
                raise RateLimitError("mesh rate limit exceeded")
            kept.append(now)
            stamps[principal.actor_id] = [
                item.strftime("%Y-%m-%dT%H:%M:%S.%fZ") for item in kept
            ]
            index["rate_stamps"] = stamps

        mutate_index(self.workspace, persist)

    def _idempotent_get(self, key: str, fingerprint: str) -> str | None:
        index = load_index(self.workspace)
        stored = dict(index.get("idempotency", {})).get(key)
        if stored is None:
            return None
        if not isinstance(stored, dict):
            raise IdempotencyConflictError("corrupt idempotency record")
        if str(stored.get("fingerprint")) != fingerprint:
            raise IdempotencyConflictError("idempotency key reused with a different payload")
        return str(stored["result_id"])

    def _idempotent_put(self, key: str, fingerprint: str, result_id: str) -> None:
        def persist(index: dict[str, Any]) -> None:
            records = dict(index.get("idempotency", {}))
            records[key] = {"fingerprint": fingerprint, "result_id": result_id}
            index["idempotency"] = records

        mutate_index(self.workspace, persist)

    def _load_credential(self, credential_id: str) -> VaultCredential:
        index = load_index(self.workspace)
        digest = dict(index.get("credential_digests", {})).get(credential_id)
        if digest is None:
            raise CredentialError(f"unknown mesh credential {credential_id}")
        return VaultCredential.from_dict(load_payload(self.workspace, str(digest)))

    def _put_credential(self, stored: VaultCredential) -> VaultCredential:
        def persist(index: dict[str, Any]) -> VaultCredential:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("credential_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["credential_ids"] = ids
            digests = dict(index.get("credential_digests", {}))
            digests[stored.id] = digest
            index["credential_digests"] = digests
            tokens = dict(index.get("token_digests", {}))
            if stored.status is CredentialStatus.ACTIVE:
                tokens[stored.token_digest] = stored.id
            else:
                tokens.pop(stored.token_digest, None)
            index["token_digests"] = tokens
            return stored

        return mutate_index(self.workspace, persist)

    def _load_capability(self, capability_id: str) -> MeshCapability:
        index = load_index(self.workspace)
        digest = dict(index.get("capability_digests", {})).get(capability_id)
        if digest is None:
            raise MeshNotFoundError(f"unknown capability {capability_id}")
        return MeshCapability.from_dict(load_payload(self.workspace, str(digest)))

    def _put_capability(self, stored: MeshCapability) -> MeshCapability:
        def persist(index: dict[str, Any]) -> MeshCapability:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("capability_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["capability_ids"] = ids
            digests = dict(index.get("capability_digests", {}))
            digests[stored.id] = digest
            index["capability_digests"] = digests
            return stored

        return mutate_index(self.workspace, persist)

    def _put_sync(self, stored: SyncRecord) -> SyncRecord:
        def persist(index: dict[str, Any]) -> SyncRecord:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("sync_ids", []))
            ids.append(stored.id)
            index["sync_ids"] = ids
            digests = dict(index.get("sync_digests", {}))
            digests[stored.id] = digest
            index["sync_digests"] = digests
            return stored

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
            object_kind="integration_mesh",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
