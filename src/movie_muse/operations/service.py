"""SBOM generation, cost caps, backup/restore drills, and incident runbooks."""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService, Resource, ResourceKind
from movie_muse.identity.api import Principal
from movie_muse.operations.errors import CostCapError, IncidentError, SbomError
from movie_muse.operations.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.operations.types import DENIED_PACKAGES, Incident, Sbom, SbomPackage
from movie_muse.persistence.api import LocalWorkspace, create_backup, restore_backup, utc_now
from movie_muse.schemas.api import new_ulid
from movie_muse.toolchain.paths import repo_root

RUNBOOK_STEPS = (
    "classify_severity",
    "snapshot_workspace",
    "restore_from_backup",
    "verify_integrity",
    "reproduce_independently",
    "close_incident",
)


def _parse_requirement_line(line: str) -> SbomPackage | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("-r "):
        return None
    name = stripped.split("==")[0].split(">=")[0].split("[")[0].strip()
    version = stripped.split("==")[1].strip() if "==" in stripped else "unpinned"
    return SbomPackage(name=name, version=version, source="requirements-dev.txt")


def collect_declared_packages(root: Path | None = None) -> tuple[SbomPackage, ...]:
    base = root or repo_root()
    packages: list[SbomPackage] = []
    pyproject = tomllib.loads((base / "pyproject.toml").read_text(encoding="utf-8"))
    project = dict(pyproject.get("project") or {})
    packages.append(
        SbomPackage(
            name=str(project.get("name", "movie-muse")),
            version=str(project.get("version", "0")),
            source="pyproject.toml",
        )
    )
    requirements = base / "requirements-dev.txt"
    if requirements.is_file():
        for line in requirements.read_text(encoding="utf-8").splitlines():
            parsed = _parse_requirement_line(line)
            if parsed is not None:
                packages.append(parsed)
    return tuple(packages)


class OperationsService:
    """Backup/restore and cost controls. Incident close requires an independent drill."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        *,
        organization_id: str,
        project_id: str,
        ready_check: Callable[[], None] | None = None,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.organization_id = organization_id
        self.project_id = project_id
        self._ready_check = ready_check or (lambda: None)

    def _resource(self) -> Resource:
        return Resource(
            kind=ResourceKind.PROJECT,
            id=self.project_id,
            organization_id=self.organization_id,
            project_id=self.project_id,
        )

    def _require(self, principal: Principal, action: Action, acl_epoch: int) -> None:
        self.authorization.require(principal, action, self._resource(), acl_epoch=acl_epoch)

    def generate_sbom(self, *, principal: Principal, acl_epoch: int) -> Sbom:
        self._require(principal, Action.MANAGE_ACL, acl_epoch)
        packages = collect_declared_packages()
        denied = [item.name for item in packages if item.name.lower() in DENIED_PACKAGES]
        if denied:
            raise SbomError(f"denied packages in SBOM: {denied}")
        record = Sbom(id=f"sbm_{new_ulid()}", packages=packages, created_at=utc_now())
        digest = put_payload(self.workspace, record.to_dict())

        def persist(index: dict[str, Any]) -> None:
            ids = list(index.get("sbom_ids", []))
            ids.append(record.id)
            index["sbom_ids"] = ids
            digests = dict(index.get("sbom_digests", {}))
            digests[record.id] = digest
            index["sbom_digests"] = digests

        mutate_index(self.workspace, persist)
        return record

    def latest_sbom(self) -> Sbom:
        index = load_index(self.workspace)
        ids = list(index.get("sbom_ids", []))
        if not ids:
            raise SbomError("no SBOM has been generated")
        digest = dict(index.get("sbom_digests", {}))[str(ids[-1])]
        return Sbom.from_dict(load_payload(self.workspace, str(digest)))

    def backup(self, destination: Path) -> Path:
        return create_backup(self.workspace.store, destination)

    def restore_into(self, store_root: Path, backup_dir: Path) -> None:
        restore_backup(store_root, backup_dir)

    def set_cost_cap(self, amount: float, *, principal: Principal, acl_epoch: int) -> float:
        self._require(principal, Action.MANAGE_ACL, acl_epoch)
        if amount < 0:
            raise CostCapError("cost cap must be non-negative")

        def persist(index: dict[str, Any]) -> None:
            index["cost_cap"] = float(amount)

        mutate_index(self.workspace, persist)
        return float(amount)

    def record_spend(self, amount: float, *, principal: Principal, acl_epoch: int) -> float:
        self._require(principal, Action.RUN_PAID_PROVIDER, acl_epoch)
        index = load_index(self.workspace)
        cap = index.get("cost_cap")
        spend = float(index.get("spend", 0.0)) + float(amount)
        if cap is not None and spend > float(cap):
            raise CostCapError(f"spend {spend} exceeds cap {cap}")

        def persist(current: dict[str, Any]) -> None:
            current["spend"] = spend

        mutate_index(self.workspace, persist)
        return spend

    def assert_within_cap(self) -> None:
        index = load_index(self.workspace)
        cap = index.get("cost_cap")
        spend = float(index.get("spend", 0.0))
        if cap is not None and spend > float(cap):
            raise CostCapError(f"spend {spend} exceeds cap {cap}")

    def open_incident(
        self,
        title: str,
        *,
        severity: str,
        principal: Principal,
        acl_epoch: int,
    ) -> Incident:
        self._require(principal, Action.MANAGE_ACL, acl_epoch)
        incident = Incident(
            id=f"inc_{new_ulid()}",
            title=title.strip(),
            severity=severity.strip(),
            status="open",
            backup_path=None,
            independently_reproduced=False,
            created_at=utc_now(),
        )
        digest = put_payload(self.workspace, incident.to_dict())

        def persist(index: dict[str, Any]) -> None:
            ids = list(index.get("incident_ids", []))
            ids.append(incident.id)
            index["incident_ids"] = ids
            digests = dict(index.get("incident_digests", {}))
            digests[incident.id] = digest
            index["incident_digests"] = digests

        mutate_index(self.workspace, persist)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="operations.incident.open",
            object_kind="incident",
            object_id=incident.id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=title,
        )
        return incident

    def execute_runbook(
        self,
        incident_id: str,
        backup_dir: Path,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> Incident:
        self._require(principal, Action.MANAGE_ACL, acl_epoch)
        self._ready_check()
        path = self.backup(backup_dir)
        stored = self._load_incident(incident_id)
        updated = Incident(
            id=stored.id,
            title=stored.title,
            severity=stored.severity,
            status="runbook_executed",
            backup_path=str(path),
            independently_reproduced=False,
            created_at=stored.created_at,
        )
        return self._save_incident(updated, principal=principal, acl_epoch=acl_epoch, reason="runbook")

    def reproduce_independently(
        self,
        incident_id: str,
        restore_root: Path,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> Incident:
        self._require(principal, Action.MANAGE_ACL, acl_epoch)
        stored = self._load_incident(incident_id)
        if not stored.backup_path:
            raise IncidentError("runbook backup is required before independent reproduction")
        self.restore_into(restore_root, Path(stored.backup_path))
        marker = restore_root / "movie_muse.sqlite"
        if not marker.is_file():
            raise IncidentError("restored workspace is missing the sqlite database")
        updated = Incident(
            id=stored.id,
            title=stored.title,
            severity=stored.severity,
            status="reproduced",
            backup_path=stored.backup_path,
            independently_reproduced=True,
            created_at=stored.created_at,
        )
        return self._save_incident(
            updated, principal=principal, acl_epoch=acl_epoch, reason="independent_reproduction"
        )

    def close_incident(self, incident_id: str, *, principal: Principal, acl_epoch: int) -> Incident:
        self._require(principal, Action.MANAGE_ACL, acl_epoch)
        stored = self._load_incident(incident_id)
        if not stored.independently_reproduced:
            raise IncidentError("incident cannot close until independently reproduced")
        updated = Incident(
            id=stored.id,
            title=stored.title,
            severity=stored.severity,
            status="closed",
            backup_path=stored.backup_path,
            independently_reproduced=True,
            created_at=stored.created_at,
            closed_at=utc_now(),
        )
        return self._save_incident(updated, principal=principal, acl_epoch=acl_epoch, reason="close")

    def list_incidents(self) -> tuple[Incident, ...]:
        index = load_index(self.workspace)
        items: list[Incident] = []
        for incident_id in index.get("incident_ids", []):
            digest = dict(index.get("incident_digests", {})).get(str(incident_id))
            if digest:
                items.append(Incident.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(items)

    def _load_incident(self, incident_id: str) -> Incident:
        index = load_index(self.workspace)
        digest = dict(index.get("incident_digests", {})).get(incident_id)
        if digest is None:
            raise IncidentError(f"unknown incident: {incident_id}")
        return Incident.from_dict(load_payload(self.workspace, str(digest)))

    def _save_incident(
        self,
        incident: Incident,
        *,
        principal: Principal,
        acl_epoch: int,
        reason: str,
    ) -> Incident:
        digest = put_payload(self.workspace, incident.to_dict())

        def persist(index: dict[str, Any]) -> None:
            digests = dict(index.get("incident_digests", {}))
            digests[incident.id] = digest
            index["incident_digests"] = digests

        mutate_index(self.workspace, persist)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=f"operations.incident.{reason}",
            object_kind="incident",
            object_id=incident.id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
        return incident
