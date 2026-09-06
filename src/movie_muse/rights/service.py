"""Permissioned, local-first rights registry and permitted-use policy."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any, TypeVar

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.identity.api import Principal, PrincipalKind
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.rights.errors import (
    HumanValidationError,
    PermittedUseDeniedError,
    SourceImmutableError,
    SourceNotFoundError,
    UnlicensedSourceError,
)
from movie_muse.rights.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.rights.types import (
    PermittedUse,
    PermittedUseDecision,
    SourceClassification,
    SourceDisclosure,
    SourceOrigin,
    SourceValidationState,
    SourceVersion,
    classification_basis,
    parse_classification,
    parse_permitted_use,
)
from movie_muse.schemas.api import RightsRecord, new_id, new_ulid

T = TypeVar("T")


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class RightsService:
    """Register sources, version them immutably, and fail closed on disallowed use."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog | None = None,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit or AuditLog(workspace)

    def register_source(
        self,
        *,
        project_id: str,
        title: str,
        classification: SourceClassification | str,
        principal: Principal,
        acl_epoch: int,
        permitted_uses: Iterable[PermittedUse | str] = (),
        uri: str | None = None,
        license_summary: str | None = None,
        license_expiry: str | None = None,
        allow_training: bool = False,
        source_id: str | None = None,
    ) -> SourceVersion:
        parsed = parse_classification(classification)
        uses = tuple(parse_permitted_use(item) for item in permitted_uses)
        origin = (
            SourceOrigin.INTEGRATION
            if principal.kind is PrincipalKind.INTEGRATION_SERVICE
            else SourceOrigin.HUMAN
        )
        self._require_registry_write(principal, project_id, acl_epoch, origin=origin)
        now = utc_now()
        if origin is SourceOrigin.HUMAN:
            validation_state = SourceValidationState.VALIDATED
            validated_by = principal.actor_id
            validated_at = now
        else:
            validation_state = SourceValidationState.UNVALIDATED
            validated_by = None
            validated_at = None
        version = self._new_version(
            source_id=source_id or f"src_{new_ulid()}",
            version=1,
            project_id=project_id,
            title=title,
            classification=parsed,
            permitted_uses=uses,
            registered_by=principal.actor_id,
            registered_at=now,
            origin=origin,
            validation_state=validation_state,
            allow_training=allow_training,
            uri=uri,
            license_summary=license_summary,
            license_expiry=license_expiry,
            validated_by=validated_by,
            validated_at=validated_at,
        )
        stored = self._write_index(lambda index: self._persist_version(index, version))
        self._audit(
            principal,
            operation="rights_register_source",
            object_id=stored.source_id,
            acl_epoch=acl_epoch,
            reason=f"{stored.origin.value}:{stored.classification.value}",
        )
        return stored

    def update_source(
        self,
        source_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        title: str | None = None,
        classification: SourceClassification | str | None = None,
        permitted_uses: Iterable[PermittedUse | str] | None = None,
        uri: str | None = None,
        license_summary: str | None = None,
        license_expiry: str | None = None,
        allow_training: bool | None = None,
    ) -> SourceVersion:
        current = self._latest(source_id)
        origin = (
            SourceOrigin.INTEGRATION
            if principal.kind is PrincipalKind.INTEGRATION_SERVICE
            else SourceOrigin.HUMAN
        )
        self._require_registry_write(
            principal, current.project_id, acl_epoch, origin=origin
        )
        now = utc_now()
        if origin is SourceOrigin.HUMAN:
            validation_state = SourceValidationState.VALIDATED
            validated_by = principal.actor_id
            validated_at = now
        else:
            validation_state = SourceValidationState.UNVALIDATED
            validated_by = None
            validated_at = None
        uses = (
            current.permitted_uses
            if permitted_uses is None
            else tuple(parse_permitted_use(item) for item in permitted_uses)
        )
        parsed = (
            current.classification
            if classification is None
            else parse_classification(classification)
        )
        version = self._new_version(
            source_id=current.source_id,
            version=current.version + 1,
            project_id=current.project_id,
            title=current.title if title is None else title,
            classification=parsed,
            permitted_uses=uses,
            registered_by=principal.actor_id,
            registered_at=now,
            origin=origin,
            validation_state=validation_state,
            allow_training=current.allow_training if allow_training is None else allow_training,
            uri=current.uri if uri is None else uri,
            license_summary=current.license_summary if license_summary is None else license_summary,
            license_expiry=current.license_expiry if license_expiry is None else license_expiry,
            validated_by=validated_by,
            validated_at=validated_at,
        )
        stored = self._write_index(lambda index: self._persist_version(index, version))
        self._audit(
            principal,
            operation="rights_update_source",
            object_id=stored.source_id,
            acl_epoch=acl_epoch,
            reason=f"version:{stored.version}",
        )
        return stored

    def validate_source(
        self,
        source_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        accept: bool = True,
    ) -> SourceVersion:
        current = self._latest(source_id)
        if principal.kind is not PrincipalKind.HUMAN:
            raise HumanValidationError("integration principals cannot validate rights records")
        self._require_view_rights(principal, current.project_id, acl_epoch)
        now = utc_now()
        state = (
            SourceValidationState.VALIDATED if accept else SourceValidationState.REJECTED
        )
        version = self._new_version(
            source_id=current.source_id,
            version=current.version + 1,
            project_id=current.project_id,
            title=current.title,
            classification=current.classification,
            permitted_uses=current.permitted_uses,
            registered_by=principal.actor_id,
            registered_at=now,
            origin=SourceOrigin.HUMAN,
            validation_state=state,
            allow_training=current.allow_training,
            uri=current.uri,
            license_summary=current.license_summary,
            license_expiry=current.license_expiry,
            validated_by=principal.actor_id if accept else None,
            validated_at=now if accept else None,
        )
        stored = self._write_index(lambda index: self._persist_version(index, version))
        self._audit(
            principal,
            operation="rights_validate_source",
            object_id=stored.source_id,
            acl_epoch=acl_epoch,
            reason=state.value,
        )
        return stored

    def get_source(
        self, source_id: str, *, principal: Principal, acl_epoch: int
    ) -> SourceVersion:
        version = self._latest(source_id)
        self._require_view_rights(principal, version.project_id, acl_epoch)
        return version

    def get_source_version(
        self, version_id: str, *, principal: Principal, acl_epoch: int
    ) -> SourceVersion:
        version = self._version(version_id)
        self._require_view_rights(principal, version.project_id, acl_epoch)
        return version

    def list_sources(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[SourceVersion, ...]:
        self._require_view_rights(principal, project_id, acl_epoch)
        index = load_index(self.workspace)
        versions: list[SourceVersion] = []
        for source_id in index["source_ids"]:
            head = index["source_head"].get(str(source_id))
            if head is None:
                continue
            version = SourceVersion.from_dict(
                load_payload(self.workspace, str(index["version_digests"][str(head)]))
            )
            if version.project_id == project_id:
                versions.append(version)
        return tuple(versions)

    def list_source_versions(
        self, source_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[SourceVersion, ...]:
        latest = self._latest(source_id)
        self._require_view_rights(principal, latest.project_id, acl_epoch)
        index = load_index(self.workspace)
        return tuple(
            SourceVersion.from_dict(
                load_payload(self.workspace, str(index["version_digests"][str(version_id)]))
            )
            for version_id in index["source_versions"].get(source_id, [])
        )

    def get_rights_record(
        self, rights_record_id: str, *, principal: Principal, acl_epoch: int
    ) -> RightsRecord:
        record = self._rights_record(rights_record_id)
        source = self._latest(record.source_id)
        self._require_view_rights(principal, source.project_id, acl_epoch)
        return record

    def query_permitted_use(
        self, source_id: str, use: PermittedUse | str, *, at: str | None = None
    ) -> PermittedUseDecision:
        parsed = parse_permitted_use(use)
        version = self._latest(source_id)
        reason = self._denial_reason(version, parsed, at=at or utc_now())
        allowed = reason is None
        return PermittedUseDecision(
            allowed=allowed,
            source_id=version.source_id,
            version_id=version.id,
            use=parsed,
            reason="permitted" if allowed else str(reason),
            rights_record_id=version.rights_record_id,
            license_summary=version.license_summary,
            validation_state=version.validation_state,
        )

    def require_permitted_use(
        self, source_id: str, use: PermittedUse | str, *, at: str | None = None
    ) -> PermittedUseDecision:
        decision = self.query_permitted_use(source_id, use, at=at)
        if decision.allowed:
            return decision
        version = self._latest(source_id)
        if version.is_unlicensed or decision.reason == "unlicensed":
            raise UnlicensedSourceError(
                f"source {source_id} is unlicensed/disallowed for {decision.use.value}"
            )
        raise PermittedUseDeniedError(
            f"source {source_id} does not permit {decision.use.value} ({decision.reason})"
        )

    def export_source_disclosure(
        self, source_id: str, *, principal: Principal, acl_epoch: int
    ) -> SourceDisclosure:
        version = self._latest(source_id)
        self._require_view_rights(principal, version.project_id, acl_epoch)
        self.require_permitted_use(source_id, PermittedUse.EXPORT_DISCLOSURE)
        disclosure = SourceDisclosure(
            source_id=version.source_id,
            version_id=version.id,
            title=version.title,
            classification=version.classification,
            license_summary=version.license_summary,
            license_expiry=version.license_expiry,
            permitted_uses=version.permitted_uses,
            validation_state=version.validation_state,
            validated_by=version.validated_by,
            validated_at=version.validated_at,
            rights_record_id=version.rights_record_id,
            exported_at=utc_now(),
            exported_by=principal.actor_id,
        )
        self._audit(
            principal,
            operation="rights_export_disclosure",
            object_id=version.source_id,
            acl_epoch=acl_epoch,
            reason=version.validation_state.value,
        )
        return disclosure

    def citation_fields(self, source_id: str, *, use: PermittedUse | str) -> PermittedUseDecision:
        """Policy check used by provenance. Does not require VIEW_RIGHTS."""

        return self.require_permitted_use(source_id, use)

    def _new_version(
        self,
        *,
        source_id: str,
        version: int,
        project_id: str,
        title: str,
        classification: SourceClassification,
        permitted_uses: tuple[PermittedUse, ...],
        registered_by: str,
        registered_at: str,
        origin: SourceOrigin,
        validation_state: SourceValidationState,
        allow_training: bool,
        uri: str | None,
        license_summary: str | None,
        license_expiry: str | None,
        validated_by: str | None,
        validated_at: str | None,
    ) -> SourceVersion:
        if allow_training and classification not in {
            SourceClassification.USER_OWNED,
            SourceClassification.LICENSED,
        }:
            raise PermittedUseDeniedError(
                "allow_training requires an explicit user_owned or licensed basis"
            )
        basis = classification_basis(classification)
        rights_record_id: str | None = None
        if basis is not None:
            rights_record_id = new_id("rights_record")
        return SourceVersion(
            id=f"srcv_{new_ulid()}",
            source_id=source_id,
            version=version,
            project_id=project_id,
            title=title,
            classification=classification,
            permitted_uses=permitted_uses,
            registered_by=registered_by,
            registered_at=registered_at,
            origin=origin,
            validation_state=validation_state,
            allow_training=allow_training,
            uri=uri,
            license_summary=license_summary,
            license_expiry=license_expiry,
            rights_record_id=rights_record_id,
            validated_by=validated_by,
            validated_at=validated_at,
        )

    def _persist_version(self, index: dict[str, Any], version: SourceVersion) -> SourceVersion:
        if version.id in index["version_digests"]:
            raise SourceImmutableError(f"source version already exists: {version.id}")
        source_versions = dict(index["source_versions"])
        prior = [str(item) for item in source_versions.get(version.source_id, [])]
        if version.version == 1 and version.source_id in list(index["source_ids"]):
            raise SourceImmutableError(f"source already exists: {version.source_id}")
        if version.version > 1 and not prior:
            raise SourceNotFoundError(f"unknown source: {version.source_id}")
        index["version_ids"] = [*list(index["version_ids"]), version.id]
        version_digests = dict(index["version_digests"])
        version_digests[version.id] = put_payload(self.workspace, version.to_dict())
        index["version_digests"] = version_digests
        source_versions[version.source_id] = [*prior, version.id]
        index["source_versions"] = source_versions
        source_head = dict(index["source_head"])
        source_head[version.source_id] = version.id
        index["source_head"] = source_head
        if version.source_id not in list(index["source_ids"]):
            index["source_ids"] = [*list(index["source_ids"]), version.source_id]
        if version.rights_record_id is not None:
            basis = version.basis
            if basis is None:
                raise UnlicensedSourceError("licensed sources require a rights basis")
            record = RightsRecord(
                id=version.rights_record_id,
                source_id=version.source_id,
                basis=basis,
                owner_actor_id=version.registered_by,
                registered_at=version.registered_at,
                allow_training=version.allow_training,
                license_summary=version.license_summary,
                license_expiry=version.license_expiry,
            )
            rights_digests = dict(index["rights_record_digests"])
            rights_digests[record.id] = put_payload(self.workspace, record.to_dict())
            index["rights_record_digests"] = rights_digests
            index["rights_record_ids"] = [*list(index["rights_record_ids"]), record.id]
        return version

    def _latest(self, source_id: str) -> SourceVersion:
        index = load_index(self.workspace)
        head = index["source_head"].get(source_id)
        if head is None:
            raise SourceNotFoundError(f"unknown source: {source_id}")
        return SourceVersion.from_dict(
            load_payload(self.workspace, str(index["version_digests"][str(head)]))
        )

    def _version(self, version_id: str) -> SourceVersion:
        index = load_index(self.workspace)
        digest = index["version_digests"].get(version_id)
        if digest is None:
            raise SourceNotFoundError(f"unknown source version: {version_id}")
        return SourceVersion.from_dict(load_payload(self.workspace, str(digest)))

    def _rights_record(self, rights_record_id: str) -> RightsRecord:
        index = load_index(self.workspace)
        digest = index["rights_record_digests"].get(rights_record_id)
        if digest is None:
            raise SourceNotFoundError(f"unknown rights record: {rights_record_id}")
        return RightsRecord.from_dict(load_payload(self.workspace, str(digest)))

    def _denial_reason(
        self, version: SourceVersion, use: PermittedUse, *, at: str
    ) -> str | None:
        if version.is_unlicensed:
            return "unlicensed"
        if version.rights_record_id is None:
            return "unlicensed"
        if version.validation_state is SourceValidationState.REJECTED:
            return "rejected"
        if not version.is_human_validated:
            return "unvalidated_candidate"
        if version.license_expiry is not None and _parse_utc(version.license_expiry) <= _parse_utc(
            at
        ):
            return "license_expired"
        if use is PermittedUse.TRAINING:
            if not version.allow_training:
                return "training_not_allowed"
            if version.classification not in {
                SourceClassification.USER_OWNED,
                SourceClassification.LICENSED,
            }:
                return "training_not_allowed"
        if use not in version.permitted_uses:
            return "use_not_permitted"
        return None

    def _require_registry_write(
        self,
        principal: Principal,
        project_id: str,
        acl_epoch: int,
        *,
        origin: SourceOrigin,
    ) -> None:
        action = Action.PROPOSE if origin is SourceOrigin.INTEGRATION else Action.VIEW_RIGHTS
        if origin is SourceOrigin.INTEGRATION and principal.kind is not PrincipalKind.INTEGRATION_SERVICE:
            action = Action.VIEW_RIGHTS
        self._require(principal, action, project_id, acl_epoch)

    def _require_view_rights(self, principal: Principal, project_id: str, acl_epoch: int) -> None:
        self._require(principal, Action.VIEW_RIGHTS, project_id, acl_epoch)

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )

    def _write_index(self, mutate: Callable[[dict[str, Any]], T]) -> T:
        return mutate_index(self.workspace, mutate)

    def _audit(
        self,
        principal: Principal,
        *,
        operation: str,
        object_id: str,
        acl_epoch: int,
        reason: str,
    ) -> None:
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=operation,
            object_kind="rights_source",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
