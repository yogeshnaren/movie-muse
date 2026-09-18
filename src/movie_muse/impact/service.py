"""Map continuity findings onto semantic/continuity/production impact."""

from __future__ import annotations

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.continuity.api import (
    ContinuityFinding,
    ContinuityReport,
    ContinuityService,
    FindingCategory,
    Materiality,
)
from movie_muse.dependencies.api import DependencyEngine, NodeKind, NodeState
from movie_muse.identity.api import Principal
from movie_muse.schemas.api import ImpactSummary


class ImpactService:
    """Project continuity findings into an inspectable ImpactSummary."""

    def __init__(
        self,
        continuity: ContinuityService,
        authorization: AuthorizationService,
        audit: AuditLog,
        dependencies: DependencyEngine | None = None,
    ) -> None:
        self.continuity = continuity
        self.authorization = authorization
        self.audit = audit
        self.dependencies = dependencies

    def summarize(
        self,
        report: ContinuityReport,
        *,
        principal: Principal,
        acl_epoch: int,
        inspect_all: bool = False,
    ) -> ImpactSummary:
        self._require(principal, Action.READ, report.project_id, acl_epoch)
        findings = report.findings
        if inspect_all:
            findings = self.continuity.inspect(
                report.revision_id,
                principal=principal,
                acl_epoch=acl_epoch,
                project_id=report.project_id,
            )
        semantic = tuple(
            self._line(finding)
            for finding in findings
            if finding.category is FindingCategory.CREATIVE
            and finding.materiality is Materiality.HIGH
        )
        continuity = tuple(
            self._line(finding)
            for finding in findings
            if finding.category is FindingCategory.CREATIVE
        )
        production = tuple(
            self._line(finding)
            for finding in findings
            if finding.category is FindingCategory.LOGISTICS
            or finding.dimension.value in {"possession", "injury"}
        )
        production = (*production, *self._stale_derived(report.project_id, principal, acl_epoch))
        summary = ImpactSummary(
            semantic=semantic,
            continuity=continuity,
            production=production,
        )
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="impact.summarize",
            object_kind="impact_summary",
            object_id=report.revision_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=(
                f"semantic={len(summary.semantic)} "
                f"continuity={len(summary.continuity)} "
                f"production={len(summary.production)}"
            ),
        )
        return summary

    def consequences(
        self,
        finding: ContinuityFinding,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[str, ...]:
        self._require(principal, Action.READ, finding.project_id, acl_epoch)
        lines = (
            self._line(finding),
            f"scene:{finding.scene_id}",
            f"evidence:{','.join(finding.evidence_ids)}",
        )
        return (*lines, *self._stale_derived(finding.project_id, principal, acl_epoch))

    def _stale_derived(
        self, project_id: str, principal: Principal, acl_epoch: int
    ) -> tuple[str, ...]:
        if self.dependencies is None:
            return ()
        views = self.dependencies.list_nodes(
            project_id, principal=principal, acl_epoch=acl_epoch
        )
        return tuple(
            f"stale derived {view.id}"
            for view in views
            if view.kind is NodeKind.DERIVED_PROJECTION and view.state is NodeState.STALE
        )

    @staticmethod
    def _line(finding: ContinuityFinding) -> str:
        return (
            f"{finding.materiality.value}:{finding.dimension.value}:"
            f"{finding.attribute}:{finding.reason}"
        )

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )
