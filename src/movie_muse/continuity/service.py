"""Permissioned continuity analysis over StateEngine contradictions."""

from __future__ import annotations

import hashlib
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService, Mode
from movie_muse.continuity.errors import (
    FindingClosedError,
    FindingNotFoundError,
    HumanRequiredError,
)
from movie_muse.continuity.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.continuity.types import (
    ContinuityFinding,
    ContinuityReport,
    FindingCategory,
    FindingDisposition,
    FindingStatus,
    Materiality,
    category_for,
    materiality_for,
)
from movie_muse.identity.api import Principal, PrincipalKind
from movie_muse.persistence.api import utc_now
from movie_muse.schemas.api import (
    FilmIR,
    ProductionProjection,
    ProjectionKind,
    ScreenplayDocument,
    new_id,
    new_ulid,
)
from movie_muse.state_engine.api import (
    Contradiction,
    Reduction,
    StateEngine,
    StateFact,
    StateTransition,
)


def _stable_suffix(*parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).digest()[:10]
    return new_ulid(_time_ms=0, _random_bytes=digest)


class ContinuityService:
    """Map StateEngine contradictions onto mode-filtered, evidence-bearing findings."""

    def __init__(
        self,
        state_engine: StateEngine,
        authorization: AuthorizationService,
        audit: AuditLog,
    ) -> None:
        self.state_engine = state_engine
        self.authorization = authorization
        self.audit = audit
        self.workspace = state_engine.workspace

    def analyze(
        self,
        film_ir: FilmIR,
        document: ScreenplayDocument,
        *,
        principal: Principal,
        acl_epoch: int,
        mode: tuple[Mode, ...] = (Mode.WRITER,),
        extra_transitions: tuple[StateTransition, ...] = (),
        inspect_all: bool = False,
        persist: bool = True,
    ) -> ContinuityReport:
        self._require(principal, Action.READ, document.project_id, acl_epoch)
        reduction = self.state_engine.reduce(
            film_ir,
            document,
            principal=principal,
            acl_epoch=acl_epoch,
            extra_transitions=extra_transitions,
            persist=persist,
        )
        index = load_index(self.workspace)
        dispositions = {
            finding_id: FindingDisposition.from_dict(payload)
            for finding_id, payload in dict(index.get("dispositions", {})).items()
        }
        generated = self._findings_from_reduction(
            reduction,
            project_id=document.project_id,
            modes=mode,
            dispositions=dispositions,
        )
        visible, hidden = self._filter_findings(generated, inspect_all=inspect_all)
        projection = ProductionProjection(
            id=new_id("production_projection"),
            project_id=document.project_id,
            kind=ProjectionKind.CONTINUITY,
            source_revision_id=reduction.revision_id,
            computed_at=utc_now(),
            data={
                "mode": [item.value for item in mode],
                "finding_ids": [item.id for item in generated],
                "visible_ids": [item.id for item in visible],
            },
        )
        report = ContinuityReport(
            revision_id=reduction.revision_id,
            project_id=document.project_id,
            mode=mode,
            findings=visible,
            hidden_finding_ids=tuple(item.id for item in hidden),
            projection_id=projection.id,
        )
        if persist:
            self._persist_report(report, generated, projection)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="continuity.analyze",
            object_kind="continuity_report",
            object_id=report.revision_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=f"visible={len(visible)} hidden={len(hidden)}",
        )
        return report

    def inspect(
        self,
        revision_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        project_id: str,
    ) -> tuple[ContinuityFinding, ...]:
        """Return every stored finding, including logistics and closed items."""

        self._require(principal, Action.READ, project_id, acl_epoch)
        return self._load_findings(revision_id)

    def resolve(
        self,
        finding_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        note: str = "",
    ) -> ContinuityFinding:
        return self._close(
            finding_id,
            status=FindingStatus.RESOLVED,
            principal=principal,
            acl_epoch=acl_epoch,
            note=note,
            operation="continuity.resolve",
        )

    def suppress(
        self,
        finding_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        note: str = "",
    ) -> ContinuityFinding:
        return self._close(
            finding_id,
            status=FindingStatus.SUPPRESSED,
            principal=principal,
            acl_epoch=acl_epoch,
            note=note,
            operation="continuity.suppress",
        )

    def _close(
        self,
        finding_id: str,
        *,
        status: FindingStatus,
        principal: Principal,
        acl_epoch: int,
        note: str,
        operation: str,
    ) -> ContinuityFinding:
        if principal.kind is not PrincipalKind.HUMAN:
            raise HumanRequiredError("only a human principal may resolve or suppress findings")
        finding = self._finding(finding_id)
        self._require(principal, Action.ACCEPT, finding.project_id, acl_epoch)
        if finding.status is not FindingStatus.OPEN:
            raise FindingClosedError(f"finding {finding_id} is {finding.status.value}")
        disposition = FindingDisposition(
            status=status,
            actor_id=principal.actor_id,
            created_at=utc_now(),
            note=note,
        )
        closed = ContinuityFinding(
            id=finding.id,
            source_id=finding.source_id,
            scene_id=finding.scene_id,
            subject_id=finding.subject_id,
            dimension=finding.dimension,
            attribute=finding.attribute,
            materiality=finding.materiality,
            category=finding.category,
            status=status,
            evidence_ids=finding.evidence_ids,
            reason=finding.reason,
            revision_id=finding.revision_id,
            project_id=finding.project_id,
        )

        def persist(index: dict[str, Any]) -> ContinuityFinding:
            digest = put_payload(self.workspace, closed.to_dict())
            digests = dict(index["finding_digests"])
            digests[closed.id] = digest
            index["finding_digests"] = digests
            dispositions = dict(index["dispositions"])
            dispositions[closed.id] = disposition.to_dict()
            index["dispositions"] = dispositions
            return closed

        stored = mutate_index(self.workspace, persist)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=operation,
            object_kind="continuity_finding",
            object_id=stored.id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=note or status.value,
        )
        return stored

    def _findings_from_reduction(
        self,
        reduction: Reduction,
        *,
        project_id: str,
        modes: tuple[Mode, ...],
        dispositions: dict[str, FindingDisposition],
    ) -> tuple[ContinuityFinding, ...]:
        items: list[ContinuityFinding] = []
        for contradiction in reduction.contradictions:
            items.append(
                self._from_contradiction(
                    contradiction,
                    revision_id=reduction.revision_id,
                    project_id=project_id,
                    modes=modes,
                    dispositions=dispositions,
                )
            )
        for fact in reduction.misunderstandings:
            items.append(
                self._from_misunderstanding(
                    fact,
                    revision_id=reduction.revision_id,
                    project_id=project_id,
                    modes=modes,
                    dispositions=dispositions,
                )
            )
        return tuple(sorted(items, key=lambda item: item.id))

    def _from_contradiction(
        self,
        contradiction: Contradiction,
        *,
        revision_id: str,
        project_id: str,
        modes: tuple[Mode, ...],
        dispositions: dict[str, FindingDisposition],
    ) -> ContinuityFinding:
        finding_id = f"cnf_{_stable_suffix(contradiction.id)}"
        status = dispositions[finding_id].status if finding_id in dispositions else FindingStatus.OPEN
        return ContinuityFinding(
            id=finding_id,
            source_id=contradiction.id,
            scene_id=contradiction.scene_id,
            subject_id=contradiction.subject_id,
            dimension=contradiction.dimension,
            attribute=contradiction.attribute,
            materiality=materiality_for(contradiction.dimension, modes),
            category=category_for(contradiction.dimension),
            status=status,
            evidence_ids=contradiction.evidence_ids,
            reason=contradiction.reason,
            revision_id=revision_id,
            project_id=project_id,
        )

    def _from_misunderstanding(
        self,
        fact: StateFact,
        *,
        revision_id: str,
        project_id: str,
        modes: tuple[Mode, ...],
        dispositions: dict[str, FindingDisposition],
    ) -> ContinuityFinding:
        finding_id = f"cnf_{_stable_suffix('mis', fact.id)}"
        status = dispositions[finding_id].status if finding_id in dispositions else FindingStatus.OPEN
        return ContinuityFinding(
            id=finding_id,
            source_id=fact.id,
            scene_id=fact.valid_from_scene_id,
            subject_id=fact.subject_id,
            dimension=fact.dimension,
            attribute=fact.attribute,
            materiality=materiality_for(fact.dimension, modes),
            category=FindingCategory.CREATIVE,
            status=status,
            evidence_ids=fact.evidence_ids,
            reason=f"misunderstanding:{fact.subject_id}:{fact.attribute}:{fact.value}",
            revision_id=revision_id,
            project_id=project_id,
        )

    def _filter_findings(
        self,
        findings: tuple[ContinuityFinding, ...],
        *,
        inspect_all: bool,
    ) -> tuple[tuple[ContinuityFinding, ...], tuple[ContinuityFinding, ...]]:
        visible: list[ContinuityFinding] = []
        hidden: list[ContinuityFinding] = []
        for finding in findings:
            if inspect_all:
                visible.append(finding)
                continue
            if finding.status is not FindingStatus.OPEN:
                hidden.append(finding)
                continue
            if finding.materiality is Materiality.LOW:
                hidden.append(finding)
                continue
            visible.append(finding)
        return tuple(visible), tuple(hidden)

    def _persist_report(
        self,
        report: ContinuityReport,
        generated: tuple[ContinuityFinding, ...],
        projection: ProductionProjection,
    ) -> None:
        def persist(index: dict[str, Any]) -> None:
            report_digest = put_payload(self.workspace, report.to_dict())
            by_revision = dict(index["report_by_revision"])
            by_revision[report.revision_id] = report_digest
            index["report_by_revision"] = by_revision
            ids_by_revision = dict(index["finding_ids_by_revision"])
            ids_by_revision[report.revision_id] = [item.id for item in generated]
            index["finding_ids_by_revision"] = ids_by_revision
            digests = dict(index["finding_digests"])
            for finding in generated:
                digests[finding.id] = put_payload(self.workspace, finding.to_dict())
            index["finding_digests"] = digests
            projections = dict(index["projection_by_revision"])
            projections[report.revision_id] = put_payload(self.workspace, projection.to_dict())
            index["projection_by_revision"] = projections

        mutate_index(self.workspace, persist)

    def _load_findings(self, revision_id: str) -> tuple[ContinuityFinding, ...]:
        index = load_index(self.workspace)
        ids = list(index.get("finding_ids_by_revision", {}).get(revision_id, ()))
        findings: list[ContinuityFinding] = []
        for finding_id in ids:
            digest = index["finding_digests"].get(finding_id)
            if digest is None:
                continue
            findings.append(ContinuityFinding.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(findings)

    def _finding(self, finding_id: str) -> ContinuityFinding:
        index = load_index(self.workspace)
        digest = index["finding_digests"].get(finding_id)
        if digest is None:
            raise FindingNotFoundError(f"unknown finding: {finding_id}")
        return ContinuityFinding.from_dict(load_payload(self.workspace, str(digest)))

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )
