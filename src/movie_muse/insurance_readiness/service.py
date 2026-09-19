"""Reviewed insurance-readiness packets over current schedule and budget."""

from __future__ import annotations

from collections.abc import Callable
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
from movie_muse.breakdown.api import BreakdownService, ElementKind, VerificationState
from movie_muse.budget.api import BudgetService
from movie_muse.dependencies.api import DependencyEngine, NodeKind, NodeState
from movie_muse.identity.api import Principal, PrincipalKind
from movie_muse.insurance_readiness.errors import (
    CoverageClaimError,
    HandoffNotAuthorizedError,
    PacketNotFoundError,
    StaleInputsError,
)
from movie_muse.insurance_readiness.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.insurance_readiness.types import (
    DISCLAIMER,
    FORBIDDEN_COVERAGE_PHRASES,
    EvidenceItem,
    HandoffPreview,
    MissingItem,
    RiskItem,
    StoredPacket,
)
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.scheduling.api import ScheduleService
from movie_muse.schemas.api import (
    ArtifactStatus,
    ProductionProjection,
    ProjectionKind,
    new_id,
    new_ulid,
)

TEMPLATE_ID = "tmpl_insurance_readiness"
TEMPLATE_VERSION = "1"
RENDERER_VERSION = "json/1"
TEMPLATE_BODY = (
    "{disclaimer}\n\n"
    "PROJECT {project_id}\nSCHEDULE {schedule_id}\nBUDGET {budget_id}\n"
    "RISKS {risks}\nMISSING {missing}\nEVIDENCE {evidence}\n"
)
RISK_KINDS = frozenset(
    {
        ElementKind.STUNT,
        ElementKind.MINOR,
        ElementKind.ANIMAL,
        ElementKind.SAFETY,
        ElementKind.INTIMACY,
    }
)
EVIDENCE_KINDS = frozenset({ElementKind.CAST, ElementKind.LOCATION, ElementKind.STUNT})


class InsuranceReadinessService:
    """Readiness support packet. Not underwriting, binding, or coverage."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        artifacts: ArtifactService,
        budgets: BudgetService,
        schedules: ScheduleService,
        breakdowns: BreakdownService,
        *,
        dependencies: DependencyEngine | None = None,
        live_partner_configured: bool = False,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.artifacts = artifacts
        self.budgets = budgets
        self.schedules = schedules
        self.breakdowns = breakdowns
        self.dependencies = dependencies
        self.live_partner_configured = live_partner_configured
        self.clock = clock

    def compile(
        self,
        budget_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredPacket:
        budget = self.budgets.get_budget(budget_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, budget.project_id, acl_epoch)
        self._require_financial(principal, budget.project_id, acl_epoch)
        if budget.labeled_stale or budget.projection.is_stale:
            raise StaleInputsError("stale budget cannot be labeled current readiness")
        schedule = self.schedules.get_schedule(
            budget.schedule_id, principal=principal, acl_epoch=acl_epoch
        )
        if schedule.labeled_stale or schedule.projection.is_stale:
            raise StaleInputsError("stale schedule cannot be labeled current readiness")
        breakdown = self.breakdowns.get_breakdown(
            schedule.breakdown_id, principal=principal, acl_epoch=acl_epoch
        )
        risks = self._risks(breakdown.elements)
        missing = self._missing(breakdown.elements, schedule, budget)
        evidence = self._evidence(breakdown.elements, schedule, budget)
        disclosures = (
            DISCLAIMER,
            "Cast, location, and stunt evidence is copied from the locked breakdown.",
            "Schedule board count and budget total are inputs, not coverage limits.",
        )
        self._ensure_template(budget.project_id, principal, acl_epoch)
        artifact = self.artifacts.create_artifact(
            project_id=budget.project_id,
            artifact_type=ArtifactType.PACKAGE,
            title="Insurance readiness support",
            principal=principal,
            acl_epoch=acl_epoch,
        )
        version = self.artifacts.create_version(
            artifact.id,
            inputs={
                "disclaimer": DISCLAIMER,
                "project_id": budget.project_id,
                "schedule_id": schedule.id,
                "budget_id": budget.id,
                "risks": ",".join(item.kind for item in risks) or "none",
                "missing": ",".join(item.code for item in missing) or "none",
                "evidence": ",".join(item.kind for item in evidence) or "none",
            },
            source_revision_id=schedule.projection.source_revision_id,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            renderer_version=RENDERER_VERSION,
            classification=ArtifactClassification.RESTRICTED,
            principal=principal,
            acl_epoch=acl_epoch,
        )
        packet = StoredPacket(
            projection=ProductionProjection(
                id=new_id("production_projection"),
                project_id=budget.project_id,
                kind=ProjectionKind.INSURANCE_READINESS,
                source_revision_id=schedule.projection.source_revision_id,
                computed_at=self.clock(),
                data={
                    "budget_id": budget.id,
                    "schedule_id": schedule.id,
                    "disclaimer": DISCLAIMER,
                },
                is_stale=False,
            ),
            budget_id=budget.id,
            schedule_id=schedule.id,
            breakdown_id=breakdown.projection.id,
            disclaimer=DISCLAIMER,
            risks=risks,
            missing=missing,
            evidence=evidence,
            disclosures=disclosures,
            artifact_id=artifact.id,
            artifact_version_id=version.version.id,
        )
        written = self._put(packet)
        if written.config_node_id is None:
            written = self._attach_dependency_nodes(written, principal, acl_epoch)
        self._audit(principal, acl_epoch, "insurance.compile", written.id, "readiness_support")
        return written

    def get_packet(
        self, packet_id: str, *, principal: Principal, acl_epoch: int
    ) -> StoredPacket:
        stored = self._load(packet_id)
        self._require(principal, Action.READ, stored.project_id, acl_epoch)
        self._require_financial(principal, stored.project_id, acl_epoch)
        return self._with_freshness(stored, principal, acl_epoch)

    def preview(
        self, packet_id: str, *, principal: Principal, acl_epoch: int, recipient: str
    ) -> HandoffPreview:
        stored = self.get_packet(packet_id, principal=principal, acl_epoch=acl_epoch)
        rendered = self.artifacts.render_version(
            stored.artifact_version_id,
            principal=principal,
            acl_epoch=acl_epoch,
            purpose=RenderPurpose.PREVIEW,
        )
        content = rendered.content.decode("utf-8")
        self._assert_not_coverage(content)
        updated = self._clone(stored, previewed=True)
        self._put(updated)
        preview = HandoffPreview(
            packet_id=stored.id,
            recipient=recipient,
            content=content,
            render_id=rendered.render.id,
            checksum=rendered.render.checksum,
            channel="broker_sandbox",
        )
        self._audit(principal, acl_epoch, "insurance.preview", stored.id, recipient)
        return preview

    def approve(
        self, packet_id: str, *, principal: Principal, acl_epoch: int
    ) -> StoredPacket:
        if principal.kind is not PrincipalKind.HUMAN:
            raise HandoffNotAuthorizedError("only a human principal may approve readiness handoff")
        stored = self.get_packet(packet_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.ACCEPT, stored.project_id, acl_epoch)
        if not stored.previewed:
            raise HandoffNotAuthorizedError("approve requires a preview of the packet")
        if stored.labeled_stale or stored.projection.is_stale:
            raise StaleInputsError("stale readiness packet cannot be approved as current")
        self.artifacts.transition_review(
            stored.artifact_version_id,
            ArtifactStatus.IN_REVIEW,
            principal=principal,
            acl_epoch=acl_epoch,
        )
        self.artifacts.transition_review(
            stored.artifact_version_id,
            ArtifactStatus.APPROVED,
            principal=principal,
            acl_epoch=acl_epoch,
        )
        written = self._put(self._clone(stored, previewed=True, approved=True))
        self._audit(principal, acl_epoch, "insurance.approve", written.id, "readiness_support")
        return written

    def handoff(
        self,
        packet_id: str,
        *,
        preview: HandoffPreview,
        confirm: bool,
        principal: Principal,
        acl_epoch: int,
    ) -> DeliveryRecord:
        stored = self.get_packet(packet_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.EXPORT, stored.project_id, acl_epoch)
        self._require_financial(principal, stored.project_id, acl_epoch)
        if stored.labeled_stale or stored.projection.is_stale:
            raise StaleInputsError("stale readiness packet cannot be handed off as current")
        if not confirm:
            raise HandoffNotAuthorizedError("handoff requires explicit confirm=True after preview")
        if preview.packet_id != stored.id:
            raise HandoffNotAuthorizedError("preview does not match the packet")
        if not stored.previewed or not stored.approved:
            raise HandoffNotAuthorizedError("handoff requires previewed and approved packet")
        self._assert_not_coverage(preview.content)
        delivery = self.artifacts.deliver(
            stored.artifact_version_id,
            preview_render_id=preview.render_id,
            preview_checksum=preview.checksum,
            channel=preview.channel,
            recipient=preview.recipient,
            confirm=True,
            principal=principal,
            acl_epoch=acl_epoch,
        )
        if delivery.network_sent:
            raise HandoffNotAuthorizedError("live broker send is not enabled for this packet")
        self._audit(principal, acl_epoch, "insurance.handoff", stored.id, "local_record")
        return delivery

    def export_packet(
        self, packet_id: str, *, principal: Principal, acl_epoch: int
    ) -> str:
        stored = self.get_packet(packet_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.EXPORT, stored.project_id, acl_epoch)
        if stored.labeled_stale or stored.projection.is_stale:
            raise StaleInputsError("stale readiness packet cannot be exported as current")
        lines = [
            DISCLAIMER,
            f"PACKET {stored.id}",
            f"BUDGET {stored.budget_id}",
            f"SCHEDULE {stored.schedule_id}",
            f"RISKS {len(stored.risks)}",
        ]
        for evidence in stored.evidence:
            lines.append(f"EVIDENCE {evidence.kind}\t{evidence.name}\t{evidence.detail}")
        for missing in stored.missing:
            lines.append(f"MISSING {missing.code}\t{missing.detail}")
        text = "\n".join(lines)
        self._assert_not_coverage(text)
        self._audit(principal, acl_epoch, "insurance.export", stored.id, "readiness_support")
        return text

    def notify_inputs_changed(
        self,
        *,
        budget_id: str | None = None,
        schedule_id: str | None = None,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[str, ...]:
        index = load_index(self.workspace)
        packet_ids: list[str] = []
        if budget_id:
            packet_ids.extend(list(dict(index.get("by_budget", {})).get(budget_id, [])))
        if schedule_id:
            packet_ids.extend(list(dict(index.get("by_schedule", {})).get(schedule_id, [])))
        stale_ids: list[str] = []
        for packet_id in dict.fromkeys(packet_ids):
            stored = self.get_packet(packet_id, principal=principal, acl_epoch=acl_epoch)
            if self.dependencies is not None and stored.config_node_id:
                self.dependencies.invalidate_inputs(
                    [stored.config_node_id],
                    principal=principal,
                    acl_epoch=acl_epoch,
                )
            marked = self._put(self._with_projection_stale(stored, stale=True))
            stale_ids.append(marked.id)
        self._audit(
            principal,
            acl_epoch,
            "insurance.notify_inputs_changed",
            budget_id or schedule_id or "",
            ",".join(stale_ids),
        )
        return tuple(stale_ids)

    def _risks(self, elements: tuple[Any, ...]) -> tuple[RiskItem, ...]:
        items: list[RiskItem] = []
        for element in elements:
            if element.kind not in RISK_KINDS:
                continue
            scenes = tuple(
                item.scene_id for item in element.evidence if item.scene_id is not None
            )
            excerpt = element.evidence[0].excerpt if element.evidence else ""
            items.append(
                RiskItem(
                    id=f"rsk_{new_ulid()}",
                    kind=element.kind.value,
                    name=element.name,
                    scene_ids=scenes,
                    evidence_excerpt=excerpt,
                    verified=element.verification is not VerificationState.DERIVED,
                )
            )
        return tuple(items)

    def _missing(self, elements: tuple[Any, ...], schedule: Any, budget: Any) -> tuple[MissingItem, ...]:
        missing: list[MissingItem] = []
        for element in elements:
            if element.kind in RISK_KINDS and element.verification is VerificationState.DERIVED:
                missing.append(
                    MissingItem(
                        code="unverified_risk",
                        detail=f"{element.kind.value}:{element.name} is derived, not human-verified",
                    )
                )
        if not schedule.boards:
            missing.append(MissingItem(code="empty_schedule", detail="schedule has no boards"))
        if not budget.lines:
            missing.append(MissingItem(code="empty_budget", detail="budget has no lines"))
        return tuple(missing)

    def _evidence(self, elements: tuple[Any, ...], schedule: Any, budget: Any) -> tuple[EvidenceItem, ...]:
        items = [
            EvidenceItem(
                kind="schedule",
                name=schedule.id,
                detail=f"{len(schedule.boards)} boards",
            ),
            EvidenceItem(
                kind="budget",
                name=budget.id,
                detail=f"total {budget.total} {budget.currency}",
            ),
        ]
        for element in elements:
            if element.kind not in EVIDENCE_KINDS:
                continue
            excerpt = element.evidence[0].excerpt if element.evidence else ""
            items.append(
                EvidenceItem(kind=element.kind.value, name=element.name, detail=excerpt)
            )
        return tuple(items)

    def _assert_not_coverage(self, text: str) -> None:
        lowered = text.casefold()
        for phrase in FORBIDDEN_COVERAGE_PHRASES:
            if phrase in lowered:
                raise CoverageClaimError(
                    "readiness support must not be described as underwriting, binding, or coverage"
                )
        if "readiness support only" not in lowered:
            raise CoverageClaimError("packet must prominently state readiness support only")

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

    def _load(self, packet_id: str) -> StoredPacket:
        index = load_index(self.workspace)
        digest = dict(index.get("packet_digests", {})).get(packet_id)
        if digest is None:
            raise PacketNotFoundError(f"packet {packet_id} is not in the index")
        return StoredPacket.from_dict(load_payload(self.workspace, str(digest)))

    def _put(self, stored: StoredPacket) -> StoredPacket:
        def persist(index: dict[str, Any]) -> StoredPacket:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("packet_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["packet_ids"] = ids
            digests = dict(index.get("packet_digests", {}))
            digests[stored.id] = digest
            index["packet_digests"] = digests
            by_project = dict(index.get("by_project", {}))
            project_ids = list(by_project.get(stored.project_id, []))
            if stored.id not in project_ids:
                project_ids.append(stored.id)
            by_project[stored.project_id] = project_ids
            index["by_project"] = by_project
            by_budget = dict(index.get("by_budget", {}))
            budget_ids = list(by_budget.get(stored.budget_id, []))
            if stored.id not in budget_ids:
                budget_ids.append(stored.id)
            by_budget[stored.budget_id] = budget_ids
            index["by_budget"] = by_budget
            by_schedule = dict(index.get("by_schedule", {}))
            schedule_ids = list(by_schedule.get(stored.schedule_id, []))
            if stored.id not in schedule_ids:
                schedule_ids.append(stored.id)
            by_schedule[stored.schedule_id] = schedule_ids
            index["by_schedule"] = by_schedule
            return stored

        return mutate_index(self.workspace, persist)

    def _attach_dependency_nodes(
        self,
        stored: StoredPacket,
        principal: Principal,
        acl_epoch: int,
    ) -> StoredPacket:
        if self.dependencies is None:
            return stored
        config = self.dependencies.add_node(
            project_id=stored.project_id,
            kind=NodeKind.CONFIGURATION,
            principal=principal,
            acl_epoch=acl_epoch,
            subject_id=stored.id,
        )
        analysis = self.dependencies.add_node(
            project_id=stored.project_id,
            kind=NodeKind.DERIVED_PROJECTION,
            principal=principal,
            acl_epoch=acl_epoch,
            input_ids=(config.id,),
            subject_id=stored.id,
        )
        return self._put(
            self._clone(stored, config_node_id=config.id, analysis_node_id=analysis.id)
        )

    def _with_freshness(
        self, stored: StoredPacket, principal: Principal, acl_epoch: int
    ) -> StoredPacket:
        labeled = stored.labeled_stale
        if self.dependencies is not None and stored.analysis_node_id:
            view = self.dependencies.view_node(
                stored.analysis_node_id, principal=principal, acl_epoch=acl_epoch
            )
            labeled = labeled or view.state is NodeState.STALE
        budget = self.budgets.get_budget(
            stored.budget_id, principal=principal, acl_epoch=acl_epoch
        )
        schedule = self.schedules.get_schedule(
            stored.schedule_id, principal=principal, acl_epoch=acl_epoch
        )
        labeled = labeled or budget.labeled_stale or budget.projection.is_stale
        labeled = labeled or schedule.labeled_stale or schedule.projection.is_stale
        if labeled == stored.labeled_stale and stored.projection.is_stale == labeled:
            return stored
        return self._with_projection_stale(stored, stale=labeled)

    def _with_projection_stale(self, stored: StoredPacket, *, stale: bool) -> StoredPacket:
        payload = stored.projection.to_dict()
        payload["is_stale"] = stale
        return self._clone(
            stored,
            projection=ProductionProjection.from_dict(payload),
            labeled_stale=stale,
        )

    def _clone(
        self,
        stored: StoredPacket,
        *,
        projection: ProductionProjection | None = None,
        previewed: bool | None = None,
        approved: bool | None = None,
        labeled_stale: bool | None = None,
        config_node_id: str | None = None,
        analysis_node_id: str | None = None,
    ) -> StoredPacket:
        return StoredPacket(
            projection=stored.projection if projection is None else projection,
            budget_id=stored.budget_id,
            schedule_id=stored.schedule_id,
            breakdown_id=stored.breakdown_id,
            disclaimer=stored.disclaimer,
            risks=stored.risks,
            missing=stored.missing,
            evidence=stored.evidence,
            disclosures=stored.disclosures,
            artifact_id=stored.artifact_id,
            artifact_version_id=stored.artifact_version_id,
            previewed=stored.previewed if previewed is None else previewed,
            approved=stored.approved if approved is None else approved,
            labeled_stale=stored.labeled_stale if labeled_stale is None else labeled_stale,
            config_node_id=stored.config_node_id if config_node_id is None else config_node_id,
            analysis_node_id=(
                stored.analysis_node_id if analysis_node_id is None else analysis_node_id
            ),
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

    def _require_financial(self, principal: Principal, project_id: str, acl_epoch: int) -> None:
        self._require(principal, Action.VIEW_SENSITIVE_FINANCIAL, project_id, acl_epoch)

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
            object_kind="insurance_readiness",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
