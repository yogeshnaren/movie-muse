"""Threat findings, encryption/BYOK, classification, and ACL probes."""

from __future__ import annotations

from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import (
    Action,
    AuthorizationError,
    AuthorizationService,
    Resource,
    ResourceKind,
)
from movie_muse.identity.api import Principal
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.retrieval.api import PromptInjectionError, inspect_untrusted_text
from movie_muse.schemas.api import new_ulid
from movie_muse.security.crypto import derive_workspace_key, seal, unseal
from movie_muse.security.errors import OpenHighSeverityError, SecurityError
from movie_muse.security.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.security.types import (
    CLASSIFICATION_RANKS,
    REMOTE_MAX,
    FindingSeverity,
    FindingStatus,
    SealedBlob,
    ThreatFinding,
)


class SecurityService:
    """Local security authority. HIGH/CRITICAL findings block a ready declaration."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        *,
        organization_id: str,
        project_id: str,
        customer_key: bytes | None = None,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.organization_id = organization_id
        self.project_id = project_id
        self.customer_key = customer_key
        self.local_key = derive_workspace_key(project_id)

    def _resource(self) -> Resource:
        return Resource(
            kind=ResourceKind.PROJECT,
            id=self.project_id,
            organization_id=self.organization_id,
            project_id=self.project_id,
        )

    def _require(self, principal: Principal, action: Action, acl_epoch: int) -> None:
        self.authorization.require(
            principal, action, self._resource(), acl_epoch=acl_epoch
        )

    def _audit(self, principal: Principal, acl_epoch: int, operation: str, object_id: str) -> None:
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=operation,
            object_kind="security",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=operation,
        )

    def record_finding(
        self,
        *,
        title: str,
        severity: FindingSeverity | str,
        asset: str,
        principal: Principal,
        acl_epoch: int,
    ) -> ThreatFinding:
        self._require(principal, Action.MANAGE_ACL, acl_epoch)
        item = ThreatFinding(
            id=f"tfd_{new_ulid()}",
            title=title.strip(),
            severity=severity if isinstance(severity, FindingSeverity) else FindingSeverity(severity),
            status=FindingStatus.OPEN,
            asset=asset.strip(),
            created_at=utc_now(),
        )
        digest = put_payload(self.workspace, item.to_dict())

        def persist(index: dict[str, Any]) -> None:
            ids = list(index.get("finding_ids", []))
            ids.append(item.id)
            index["finding_ids"] = ids
            digests = dict(index.get("finding_digests", {}))
            digests[item.id] = digest
            index["finding_digests"] = digests

        mutate_index(self.workspace, persist)
        self._audit(principal, acl_epoch, "security.finding.record", item.id)
        return item

    def resolve_finding(
        self,
        finding_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> ThreatFinding:
        self._require(principal, Action.MANAGE_ACL, acl_epoch)
        index = load_index(self.workspace)
        stored = ThreatFinding.from_dict(
            load_payload(self.workspace, str(dict(index["finding_digests"])[finding_id]))
        )
        updated = ThreatFinding(
            id=stored.id,
            title=stored.title,
            severity=stored.severity,
            status=FindingStatus.RESOLVED,
            asset=stored.asset,
            created_at=stored.created_at,
            resolved_at=utc_now(),
        )
        digest = put_payload(self.workspace, updated.to_dict())

        def persist(index: dict[str, Any]) -> None:
            digests = dict(index.get("finding_digests", {}))
            digests[finding_id] = digest
            index["finding_digests"] = digests

        mutate_index(self.workspace, persist)
        self._audit(principal, acl_epoch, "security.finding.resolve", finding_id)
        return updated

    def list_findings(self) -> tuple[ThreatFinding, ...]:
        index = load_index(self.workspace)
        items: list[ThreatFinding] = []
        for finding_id in index.get("finding_ids", []):
            digest = dict(index.get("finding_digests", {})).get(str(finding_id))
            if digest:
                items.append(ThreatFinding.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(items)

    def assert_ready(self) -> None:
        open_high = [
            item
            for item in self.list_findings()
            if item.status is FindingStatus.OPEN
            and item.severity in {FindingSeverity.HIGH, FindingSeverity.CRITICAL}
        ]
        if open_high:
            raise OpenHighSeverityError(f"{len(open_high)} high/critical findings remain open")

    def classify(self, label: str) -> int:
        try:
            return CLASSIFICATION_RANKS[label]
        except KeyError as exc:
            raise SecurityError(f"unknown classification: {label}") from exc

    def remote_may_serve(self, label: str) -> bool:
        return self.classify(label) <= CLASSIFICATION_RANKS[REMOTE_MAX]

    def seal_secret(self, plaintext: bytes, *, use_byok: bool = False) -> SealedBlob:
        key = self.customer_key if use_byok else self.local_key
        return seal(plaintext, key, byok=use_byok)

    def open_secret(self, blob: SealedBlob) -> bytes:
        key = self.customer_key if blob.byok else self.local_key
        return unseal(blob, key)

    def probe_acl(self, principal: Principal, action: Action, *, acl_epoch: int) -> bool:
        try:
            self.authorization.require(
                principal, action, self._resource(), acl_epoch=acl_epoch
            )
        except AuthorizationError:
            return False
        return True

    def assert_no_injection(self, text: str) -> str:
        inspection = inspect_untrusted_text(text)
        if inspection.rejected:
            raise PromptInjectionError("untrusted text failed closed")
        return inspection.redacted_text
