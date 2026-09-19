"""Deletion, export, retention, no-training defaults, and residency."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService, Resource, ResourceKind
from movie_muse.identity.api import Principal
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.privacy.errors import (
    CrossUserCacheError,
    ErasedError,
    PrivacyError,
    RetentionError,
    TrainingConsentError,
)
from movie_muse.privacy.index import load_index, mutate_index
from movie_muse.privacy.types import (
    CROSS_USER_PROMPT_CACHE,
    NO_TRAINING_DEFAULT,
    PROVIDER_RETENTION,
    ErasureRecord,
    Residency,
    SubjectExport,
    TrainingPolicy,
)
from movie_muse.schemas.api import new_ulid


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class PrivacyService:
    """Visible no-training default. Erasure and export are fail-closed."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        *,
        organization_id: str,
        project_id: str,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.organization_id = organization_id
        self.project_id = project_id

    def _resource(self) -> Resource:
        return Resource(
            kind=ResourceKind.PROJECT,
            id=self.project_id,
            organization_id=self.organization_id,
            project_id=self.project_id,
        )

    def training_policy(self) -> TrainingPolicy:
        index = load_index(self.workspace)
        return TrainingPolicy(
            no_training_default=NO_TRAINING_DEFAULT,
            opt_in=bool(index.get("training_opt_in", False)),
            provider_retention=PROVIDER_RETENTION,
            cross_user_prompt_cache=CROSS_USER_PROMPT_CACHE,
        )

    def grant_training_opt_in(self, *, principal: Principal, acl_epoch: int) -> TrainingPolicy:
        self.authorization.require(
            principal, Action.MANAGE_ACL, self._resource(), acl_epoch=acl_epoch
        )
        if not NO_TRAINING_DEFAULT:
            raise TrainingConsentError("no-training default is required")

        def persist(index: dict[str, Any]) -> None:
            index["training_opt_in"] = True

        mutate_index(self.workspace, persist)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="privacy.training.opt_in",
            object_kind="privacy",
            object_id=self.project_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason="explicit opt-in",
        )
        return self.training_policy()

    def assert_training_allowed(self) -> None:
        policy = self.training_policy()
        if policy.no_training_default and not policy.opt_in:
            raise TrainingConsentError("training on user content is off by default")

    def assert_no_cross_user_cache(self) -> None:
        if CROSS_USER_PROMPT_CACHE:
            raise CrossUserCacheError("cross-user prompt cache is forbidden")

    def set_residency(self, residency: Residency | str, *, principal: Principal, acl_epoch: int) -> str:
        self.authorization.require(
            principal, Action.MANAGE_ACL, self._resource(), acl_epoch=acl_epoch
        )
        parsed = residency if isinstance(residency, Residency) else Residency(residency)

        def persist(index: dict[str, Any]) -> None:
            index["residency"] = parsed.value

        mutate_index(self.workspace, persist)
        return parsed.value

    def erase_subject(
        self,
        subject_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        retain_days: int = 30,
    ) -> ErasureRecord:
        self.authorization.require(
            principal, Action.MANAGE_ACL, self._resource(), acl_epoch=acl_epoch
        )
        now = utc_now()
        until = (_parse_iso(now) + timedelta(days=retain_days)).astimezone(UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        record = ErasureRecord(
            id=f"prv_{new_ulid()}",
            subject_id=subject_id,
            erased_at=now,
            retain_until=until,
        )

        def persist(index: dict[str, Any]) -> None:
            erased = dict(index.get("erased_subjects", {}))
            erased[subject_id] = record.to_dict()
            index["erased_subjects"] = erased
            ids = list(index.get("erasure_ids", []))
            ids.append(record.id)
            index["erasure_ids"] = ids

        mutate_index(self.workspace, persist)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="privacy.erase",
            object_kind="subject",
            object_id=subject_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason="erasure",
        )
        return record

    def assert_readable(self, subject_id: str, *, now: str | None = None) -> None:
        index = load_index(self.workspace)
        payload = dict(index.get("erased_subjects", {})).get(subject_id)
        if payload is None:
            return
        record = ErasureRecord.from_dict(dict(payload))
        stamp = now or utc_now()
        if _parse_iso(stamp) > _parse_iso(record.retain_until):
            raise RetentionError(f"{subject_id} is past retention")
        raise ErasedError(f"{subject_id} was erased")

    def export_subject(
        self,
        subject_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        payload: dict[str, Any],
    ) -> SubjectExport:
        self.authorization.require(
            principal, Action.EXPORT, self._resource(), acl_epoch=acl_epoch
        )
        self.assert_readable(subject_id)
        if "token" in payload or "password" in payload:
            raise PrivacyError("export must not include secrets")
        index = load_index(self.workspace)
        exported = SubjectExport(
            subject_id=subject_id,
            payload=dict(payload),
            residency=str(index.get("residency", "us")),
            training_opt_in=bool(index.get("training_opt_in", False)),
        )

        def persist(index: dict[str, Any]) -> None:
            exports = dict(index.get("exports", {}))
            exports[subject_id] = exported.to_dict()
            index["exports"] = exports

        mutate_index(self.workspace, persist)
        return exported
