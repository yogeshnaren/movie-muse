"""Evidence-backed investor decks. Claims must stay current; delivery is human-approved."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
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
from movie_muse.budget.api import BudgetService, StaleBudgetError
from movie_muse.commercial_forecast.api import CommercialForecast, CommercialForecastService
from movie_muse.identity.api import Principal, PrincipalKind
from movie_muse.investor_artifacts.errors import (
    ApprovalRequiredError,
    FabricatedDeliveryError,
    PackNotFoundError,
    StaleEvidenceError,
    UnsupportedClaimError,
)
from movie_muse.investor_artifacts.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.investor_artifacts.types import (
    DISCLAIMER,
    FORBIDDEN_FABRICATION_PHRASES,
    RENDERER_VERSION,
    TEMPLATE_BODY,
    TEMPLATE_ID,
    TEMPLATE_VERSION,
    Citation,
    CitedClaim,
    InvestorPack,
    PackKind,
    PackPreview,
)
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.rights.api import PermittedUse, RightsService
from movie_muse.schemas.api import ArtifactStatus, new_ulid


def assert_no_fabrication(text: str) -> str:
    lowered = f" {text.lower()} "
    for phrase in FORBIDDEN_FABRICATION_PHRASES:
        start = 0
        while True:
            found = lowered.find(phrase, start)
            if found < 0:
                break
            prefix = lowered[max(0, found - 32) : found]
            negated = any(
                marker in prefix for marker in (" not ", " never ", " not a ", " not an ")
            )
            if not negated:
                raise FabricatedDeliveryError(
                    f"investor materials must not fabricate credentials or recipients: {phrase}"
                )
            start = found + 1
    return text


class InvestorArtifactService:
    """Decks, one-pagers, and data rooms over reviewed artifacts plus current numbers."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        artifacts: ArtifactService,
        budgets: BudgetService,
        forecasts: CommercialForecastService,
        rights: RightsService,
        *,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.artifacts = artifacts
        self.budgets = budgets
        self.forecasts = forecasts
        self.rights = rights
        self.clock = clock

    def compile(
        self,
        project_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        kind: PackKind | str,
        budget_id: str,
        forecast_id: str,
        source_version_ids: Sequence[str],
        rights_source_id: str,
    ) -> InvestorPack:
        parsed = kind if isinstance(kind, PackKind) else PackKind(str(kind))
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        budget = self.budgets.get_budget(budget_id, principal=principal, acl_epoch=acl_epoch)
        if budget.project_id != project_id:
            raise UnsupportedClaimError("budget project does not match the pack project")
        if budget.labeled_stale or budget.projection.is_stale:
            raise StaleEvidenceError("stale budget cannot back a current investor pack")
        forecast = self.forecasts.get_forecast(
            forecast_id, principal=principal, acl_epoch=acl_epoch
        )
        if forecast.project_id != project_id or forecast.budget_id != budget.id:
            raise UnsupportedClaimError("forecast is not current evidence for this budget")
        if forecast.insufficient or forecast.guarantee:
            raise UnsupportedClaimError("insufficient or guaranteed scenarios cannot be cited")
        sources = tuple(str(item) for item in source_version_ids)
        if not sources:
            raise UnsupportedClaimError("investor packs require at least one reviewed source artifact")
        for version_id in sources:
            view = self.artifacts.get_version(
                version_id, principal=principal, acl_epoch=acl_epoch
            )
            if view.status is not ArtifactStatus.APPROVED:
                raise UnsupportedClaimError(
                    "source artifacts must be reviewed and approved before citation"
                )
            if view.version.artifact_id:
                parent = self.artifacts.get_artifact(
                    view.version.artifact_id, principal=principal, acl_epoch=acl_epoch
                )
                if parent.project_id != project_id:
                    raise UnsupportedClaimError("source artifact belongs to another project")
        if not rights_source_id:
            raise UnsupportedClaimError("citations require a rights source id")
        decision = self.rights.require_permitted_use(rights_source_id, PermittedUse.CITATION)
        data_as_of = forecast.scenario.data_as_of
        claims = self._claims(budget, forecast, sources, data_as_of)
        citations = (
            Citation(
                source_id=rights_source_id,
                rights_version_id=decision.version_id,
                use=PermittedUse.CITATION.value,
            ),
        )
        self._ensure_template(project_id, principal, acl_epoch)
        artifact_type = (
            ArtifactType.PACKAGE if parsed is PackKind.DATA_ROOM else ArtifactType.DOCUMENT
        )
        artifact = self.artifacts.create_artifact(
            project_id=project_id,
            artifact_type=artifact_type,
            title=f"Investor {parsed.value.replace('_', ' ')}",
            principal=principal,
            acl_epoch=acl_epoch,
        )
        version = self.artifacts.create_version(
            artifact.id,
            inputs={
                "disclaimer": DISCLAIMER,
                "kind": parsed.value,
                "project_id": project_id,
                "budget_id": budget.id,
                "forecast_id": forecast.id,
                "data_as_of": data_as_of,
                "claims": ";".join(
                    f"{item.label}={item.value} {item.unit} via {item.evidence_ref}"
                    for item in claims
                ),
                "citations": f"{rights_source_id}:{decision.version_id}",
                "sources": ",".join(sources),
            },
            source_revision_id=budget.projection.source_revision_id,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            renderer_version=RENDERER_VERSION,
            classification=ArtifactClassification.RESTRICTED,
            principal=principal,
            acl_epoch=acl_epoch,
            rights_record_ids=(rights_source_id,),
        )
        pack = InvestorPack(
            id=f"ivp_{new_ulid()}",
            project_id=project_id,
            kind=parsed,
            budget_id=budget.id,
            forecast_id=forecast.id,
            source_version_ids=sources,
            claims=claims,
            citations=citations,
            artifact_id=artifact.id,
            artifact_version_id=version.version.id,
            data_as_of=data_as_of,
            locked_budget_total=format(budget.total, "f"),
            locked_p50=str(forecast.outcome("P50").value),
            rights_source_id=rights_source_id,
        )
        written = self._put(pack)
        self._audit(principal, acl_epoch, "investor.compile", written.id, parsed.value)
        return written

    def revise(
        self,
        pack_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        note: str,
    ) -> InvestorPack:
        stored = self.get_pack(pack_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        self._assert_current(stored, principal, acl_epoch)
        cleaned = assert_no_fabrication(note.strip())
        if not cleaned:
            raise UnsupportedClaimError("editable revision needs a note citing the change")
        version = self.artifacts.create_version(
            stored.artifact_id,
            inputs={
                "disclaimer": stored.disclaimer,
                "kind": stored.kind.value,
                "project_id": stored.project_id,
                "budget_id": stored.budget_id,
                "forecast_id": stored.forecast_id,
                "data_as_of": stored.data_as_of,
                "claims": ";".join(
                    f"{item.label}={item.value} {item.unit} via {item.evidence_ref}"
                    for item in stored.claims
                ),
                "citations": ",".join(item.source_id for item in stored.citations),
                "sources": ",".join(stored.source_version_ids),
                "editor_note": cleaned,
            },
            source_revision_id=self.budgets.get_budget(
                stored.budget_id, principal=principal, acl_epoch=acl_epoch
            ).projection.source_revision_id,
            template_id=TEMPLATE_ID,
            template_version=TEMPLATE_VERSION,
            renderer_version=RENDERER_VERSION,
            classification=ArtifactClassification.RESTRICTED,
            principal=principal,
            acl_epoch=acl_epoch,
            rights_record_ids=(stored.rights_source_id,) if stored.rights_source_id else (),
        )
        updated = self._clone(
            stored,
            artifact_version_id=version.version.id,
            previewed=False,
            approved=False,
        )
        written = self._put(updated)
        self._audit(principal, acl_epoch, "investor.revise", written.id, version.version.id)
        return written

    def preview(
        self, pack_id: str, *, principal: Principal, acl_epoch: int, recipient: str
    ) -> PackPreview:
        stored = self.get_pack(pack_id, principal=principal, acl_epoch=acl_epoch)
        self._require_real_recipient(recipient)
        rendered = self.artifacts.render_version(
            stored.artifact_version_id,
            principal=principal,
            acl_epoch=acl_epoch,
            purpose=RenderPurpose.PREVIEW,
        )
        content = assert_no_fabrication(rendered.content.decode("utf-8"))
        if DISCLAIMER not in content:
            raise UnsupportedClaimError("rendered pack is missing the investor disclaimer")
        written = self._put(self._clone(stored, previewed=True))
        preview = PackPreview(
            pack_id=written.id,
            recipient=recipient.strip(),
            content=content,
            render_id=rendered.render.id,
            checksum=rendered.render.checksum,
        )
        self._audit(principal, acl_epoch, "investor.preview", written.id, recipient.strip())
        return preview

    def approve(
        self, pack_id: str, *, principal: Principal, acl_epoch: int
    ) -> InvestorPack:
        if principal.kind is not PrincipalKind.HUMAN:
            raise ApprovalRequiredError("only a human principal may approve investor materials")
        stored = self.get_pack(pack_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.ACCEPT, stored.project_id, acl_epoch)
        if not stored.previewed:
            raise ApprovalRequiredError("approve requires a preview of the pack")
        self._assert_current(stored, principal, acl_epoch)
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
        self._audit(principal, acl_epoch, "investor.approve", written.id, stored.kind.value)
        return written

    def export_pack(
        self, pack_id: str, destination: Path, *, principal: Principal, acl_epoch: int
    ) -> Path:
        stored = self.get_pack(pack_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.EXPORT, stored.project_id, acl_epoch)
        if not stored.approved:
            raise ApprovalRequiredError("export requires creator approval")
        self._assert_current(stored, principal, acl_epoch)
        path = self.artifacts.export_version(
            stored.artifact_version_id,
            destination,
            principal=principal,
            acl_epoch=acl_epoch,
        )
        content = assert_no_fabrication(path.read_text(encoding="utf-8"))
        if DISCLAIMER not in content:
            raise UnsupportedClaimError("exported pack is missing the investor disclaimer")
        self._audit(principal, acl_epoch, "investor.export", stored.id, str(path))
        return path

    def deliver(
        self,
        pack_id: str,
        *,
        preview: PackPreview,
        confirm: bool,
        principal: Principal,
        acl_epoch: int,
    ) -> DeliveryRecord:
        stored = self.get_pack(pack_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.EXPORT, stored.project_id, acl_epoch)
        if not confirm:
            raise ApprovalRequiredError("delivery requires explicit confirm=True after preview")
        if not stored.previewed or not stored.approved:
            raise ApprovalRequiredError("delivery requires a previewed and approved pack")
        if preview.pack_id != stored.id:
            raise FabricatedDeliveryError("preview does not match the pack")
        self._require_real_recipient(preview.recipient)
        self._assert_current(stored, principal, acl_epoch)
        assert_no_fabrication(preview.content)
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
            raise FabricatedDeliveryError("local investor delivery must not mark network_sent")
        self._audit(principal, acl_epoch, "investor.deliver", stored.id, preview.recipient)
        return delivery

    def get_pack(
        self, pack_id: str, *, principal: Principal, acl_epoch: int
    ) -> InvestorPack:
        stored = self._load(pack_id)
        self._require(principal, Action.READ, stored.project_id, acl_epoch)
        self._require_financial(principal, stored.project_id, acl_epoch)
        return self._with_freshness(stored, principal, acl_epoch)

    def list_packs(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[InvestorPack, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        self._require_financial(principal, project_id, acl_epoch)
        index = load_index(self.workspace)
        ids = list(dict(index.get("by_project", {})).get(project_id, []))
        return tuple(self._load(str(item_id)) for item_id in ids)

    def _claims(
        self,
        budget: Any,
        forecast: CommercialForecast,
        sources: Sequence[str],
        data_as_of: str,
    ) -> tuple[CitedClaim, ...]:
        claims = [
            CitedClaim(
                id=f"ivc_{new_ulid()}",
                label="budget_total",
                value=format(budget.total, "f"),
                unit=budget.currency,
                evidence_ref=budget.id,
                data_as_of=data_as_of,
                method="current budget evidence ledger total",
            )
        ]
        for percentile in ("P10", "P50", "P90"):
            outcome = forecast.outcome(percentile)
            trace = next(item for item in forecast.traces if item.percentile == percentile)
            if not trace.method or not trace.comparable_ids or not trace.assumption_ids:
                raise UnsupportedClaimError("forecast number is missing data/method/assumptions")
            claims.append(
                CitedClaim(
                    id=f"ivc_{new_ulid()}",
                    label=percentile.lower(),
                    value=str(outcome.value),
                    unit=outcome.unit,
                    evidence_ref=trace.budget_id,
                    data_as_of=trace.data_as_of,
                    method=trace.method,
                )
            )
        for version_id in sources:
            claims.append(
                CitedClaim(
                    id=f"ivc_{new_ulid()}",
                    label="reviewed_source",
                    value=version_id,
                    unit="artifact_version",
                    evidence_ref=version_id,
                    data_as_of=data_as_of,
                    method="approved generic artifact version lock",
                )
            )
        return tuple(claims)

    def _assert_current(
        self, stored: InvestorPack, principal: Principal, acl_epoch: int
    ) -> None:
        if stored.labeled_stale:
            raise StaleEvidenceError("stale investor pack cannot be treated as current")
        try:
            budget = self.budgets.get_budget(
                stored.budget_id, principal=principal, acl_epoch=acl_epoch
            )
        except StaleBudgetError as exc:
            raise StaleEvidenceError("stale budget cannot back a current investor pack") from exc
        if budget.labeled_stale or budget.projection.is_stale:
            raise StaleEvidenceError("stale budget cannot back a current investor pack")
        if format(budget.total, "f") != stored.locked_budget_total:
            raise StaleEvidenceError("budget total no longer matches the locked claim")
        forecast = self.forecasts.get_forecast(
            stored.forecast_id, principal=principal, acl_epoch=acl_epoch
        )
        if str(forecast.outcome("P50").value) != stored.locked_p50:
            raise StaleEvidenceError("forecast P50 no longer matches the locked claim")
        for claim in stored.claims:
            if not claim.evidence_ref or not claim.method or not claim.data_as_of:
                raise UnsupportedClaimError("untraced claim cannot be approved or exported")
        for version_id in stored.source_version_ids:
            view = self.artifacts.get_version(
                version_id, principal=principal, acl_epoch=acl_epoch
            )
            if view.status is not ArtifactStatus.APPROVED:
                raise UnsupportedClaimError("source artifact is no longer approved")

    def _with_freshness(
        self, stored: InvestorPack, principal: Principal, acl_epoch: int
    ) -> InvestorPack:
        budget = self.budgets.get_budget(
            stored.budget_id, principal=principal, acl_epoch=acl_epoch
        )
        stale = stored.labeled_stale or budget.labeled_stale or budget.projection.is_stale
        if stale == stored.labeled_stale:
            return stored
        return self._put(self._clone(stored, labeled_stale=stale))

    def _require_real_recipient(self, recipient: str) -> None:
        cleaned = recipient.strip()
        if not cleaned or "@" not in cleaned:
            raise FabricatedDeliveryError("recipient must be a real address, not a fabricated name")
        assert_no_fabrication(cleaned)

    def _ensure_template(
        self, project_id: str, principal: Principal, acl_epoch: int
    ) -> None:
        try:
            self.artifacts.get_template(
                TEMPLATE_ID, TEMPLATE_VERSION, principal=principal, acl_epoch=acl_epoch
            )
        except ArtifactTemplateNotFoundError:
            self.artifacts.register_template(
                project_id=project_id,
                version=TEMPLATE_VERSION,
                renderer_version=RENDERER_VERSION,
                body=TEMPLATE_BODY,
                principal=principal,
                acl_epoch=acl_epoch,
                template_id=TEMPLATE_ID,
            )

    def _load(self, pack_id: str) -> InvestorPack:
        index = load_index(self.workspace)
        digest = dict(index.get("pack_digests", {})).get(pack_id)
        if digest is None:
            raise PackNotFoundError(f"investor pack {pack_id} is not in the index")
        return InvestorPack.from_dict(load_payload(self.workspace, str(digest)))

    def _put(self, stored: InvestorPack) -> InvestorPack:
        def persist(index: dict[str, Any]) -> InvestorPack:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("pack_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["pack_ids"] = ids
            digests = dict(index.get("pack_digests", {}))
            digests[stored.id] = digest
            index["pack_digests"] = digests
            by_project = dict(index.get("by_project", {}))
            project_ids = list(by_project.get(stored.project_id, []))
            if stored.id not in project_ids:
                project_ids.append(stored.id)
            by_project[stored.project_id] = project_ids
            index["by_project"] = by_project
            return stored

        return mutate_index(self.workspace, persist)

    def _clone(
        self,
        stored: InvestorPack,
        *,
        artifact_version_id: str | None = None,
        previewed: bool | None = None,
        approved: bool | None = None,
        labeled_stale: bool | None = None,
    ) -> InvestorPack:
        return InvestorPack(
            id=stored.id,
            project_id=stored.project_id,
            kind=stored.kind,
            budget_id=stored.budget_id,
            forecast_id=stored.forecast_id,
            source_version_ids=stored.source_version_ids,
            claims=stored.claims,
            citations=stored.citations,
            artifact_id=stored.artifact_id,
            artifact_version_id=artifact_version_id or stored.artifact_version_id,
            data_as_of=stored.data_as_of,
            locked_budget_total=stored.locked_budget_total,
            locked_p50=stored.locked_p50,
            disclaimer=stored.disclaimer,
            previewed=stored.previewed if previewed is None else previewed,
            approved=stored.approved if approved is None else approved,
            labeled_stale=stored.labeled_stale if labeled_stale is None else labeled_stale,
            rights_source_id=stored.rights_source_id,
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
        self.authorization.require(
            principal,
            Action.VIEW_SENSITIVE_FINANCIAL,
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
            object_kind="investor_artifacts",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
