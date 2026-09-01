"""Evidence Bundles with permitted citations, lineage, and export disclosures."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Any

from movie_muse.artifacts.api import ArtifactService
from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.identity.api import Principal, PrincipalKind
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.provenance.errors import (
    EvidenceBundleNotFoundError,
    ExportDisclosureError,
    HumanValidationError,
    MissingCitationError,
)
from movie_muse.provenance.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.provenance.types import (
    BundleValidation,
    CitationInput,
    ClaimKind,
    ExportDisclosure,
    InputLineage,
    MethodProvenance,
    StoredEvidenceBundle,
    disclaimer_for,
    reject_chain_of_thought,
)
from movie_muse.rights.api import PermittedUse, RightsService
from movie_muse.schemas.api import (
    CitedSource,
    EvidenceBundle,
    HumanValidationState,
    new_id,
    new_ulid,
)


class ProvenanceService:
    """Build, validate, and export Evidence Bundles without exposing chain-of-thought."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        rights: RightsService,
        audit: AuditLog | None = None,
        artifacts: ArtifactService | None = None,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.rights = rights
        self.audit = audit or AuditLog(workspace)
        self.artifacts = artifacts

    def build_bundle(
        self,
        *,
        project_id: str,
        claim: str,
        method_summary: str,
        provenance: MethodProvenance | Mapping[str, Any],
        principal: Principal,
        acl_epoch: int,
        citations: Iterable[CitationInput | Mapping[str, Any]],
        cited_node_ids: Iterable[str] = (),
        assumptions: Iterable[str] = (),
        alternatives: Iterable[str] = (),
        counter_evidence: Iterable[str] = (),
        sensitivity: str | None = None,
        confidence: float = 0.5,
        uncertainty: str = "unspecified",
        claim_kind: ClaimKind | str = ClaimKind.CLAIM,
        lineage: InputLineage | Mapping[str, Any] | None = None,
        revision_ids: Iterable[str] = (),
        artifact_version_ids: Iterable[str] = (),
    ) -> StoredEvidenceBundle:
        citation_items = tuple(citations)
        assumption_items = tuple(assumptions)
        alternative_items = tuple(alternatives)
        counter_items = tuple(counter_evidence)
        node_ids = tuple(cited_node_ids)
        payload = {
            "claim": claim,
            "method_summary": method_summary,
            "provenance": (
                provenance.to_dict() if isinstance(provenance, MethodProvenance) else dict(provenance)
            ),
            "citations": [
                item.to_dict() if isinstance(item, CitationInput) else dict(item)
                for item in citation_items
            ],
            "assumptions": list(assumption_items),
            "alternatives": list(alternative_items),
            "counter_evidence": list(counter_items),
            "sensitivity": sensitivity,
            "uncertainty": uncertainty,
            "claim_kind": str(claim_kind.value if isinstance(claim_kind, ClaimKind) else claim_kind),
        }
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        reject_chain_of_thought(payload, field="evidence_bundle")
        kind = claim_kind if isinstance(claim_kind, ClaimKind) else ClaimKind(str(claim_kind))
        parsed_citations = tuple(self._parse_citation(item) for item in citation_items)
        if not parsed_citations:
            raise MissingCitationError("every consequential claim requires at least one permitted citation")
        cited_sources: list[CitedSource] = []
        license_parts: list[str] = []
        source_ids: list[str] = []
        for citation in parsed_citations:
            decision = self.rights.citation_fields(citation.source_id, use=PermittedUse.CITATION)
            if decision.rights_record_id is None:
                raise MissingCitationError(
                    f"source {citation.source_id} has no rights record and cannot be cited"
                )
            cited_sources.append(
                CitedSource(
                    source_id=citation.source_id,
                    rights_record_id=decision.rights_record_id,
                    excerpt_summary=citation.excerpt_summary,
                )
            )
            license_parts.append(decision.license_summary or decision.validation_state.value)
            source_ids.append(citation.source_id)
        extra = (
            InputLineage.from_dict(lineage)
            if isinstance(lineage, Mapping)
            else (lineage or InputLineage())
        )
        merged_lineage = InputLineage(
            source_ids=tuple(dict.fromkeys((*extra.source_ids, *source_ids))),
            revision_ids=tuple(dict.fromkeys((*extra.revision_ids, *tuple(revision_ids)))),
            artifact_version_ids=tuple(
                dict.fromkeys((*extra.artifact_version_ids, *tuple(artifact_version_ids)))
            ),
        )
        method = MethodProvenance.from_mapping(provenance)
        created_at = utc_now()
        bundle = EvidenceBundle(
            id=new_id("evidence_bundle"),
            claim=claim,
            method_summary=method_summary,
            model_id=method.model,
            model_version=method.model_version,
            confidence=confidence,
            created_at=created_at,
            cited_node_ids=node_ids,
            cited_sources=tuple(cited_sources),
            assumptions=assumption_items,
            alternatives=alternative_items,
            counter_evidence=counter_items,
            sensitivity=sensitivity,
            human_validation_state=HumanValidationState.UNREVIEWED,
        )
        stored = StoredEvidenceBundle(
            bundle=bundle,
            project_id=project_id,
            claim_kind=kind,
            method_provenance=method,
            lineage=merged_lineage,
            uncertainty=uncertainty,
            rights_license="; ".join(part for part in license_parts if part),
            epistemic_disclaimer=disclaimer_for(kind),
            created_by=principal.actor_id,
        )
        reject_chain_of_thought(stored.to_dict(), field="evidence_bundle")

        def mutate(index: dict[str, Any]) -> StoredEvidenceBundle:
            index["bundle_ids"] = [*index["bundle_ids"], stored.bundle.id]
            index["bundle_digests"][stored.bundle.id] = put_payload(
                self.workspace, stored.to_dict()
            )
            index["bundle_validations"][stored.bundle.id] = []
            return stored

        persisted = mutate_index(self.workspace, mutate)
        self._audit(
            principal,
            operation="provenance_build_bundle",
            object_kind="evidence_bundle",
            object_id=persisted.bundle.id,
            acl_epoch=acl_epoch,
            reason=kind.value,
        )
        return persisted

    def get_bundle(
        self, bundle_id: str, *, principal: Principal, acl_epoch: int
    ) -> StoredEvidenceBundle:
        stored = self._bundle(bundle_id)
        self._require(principal, Action.READ, stored.project_id, acl_epoch)
        return self._with_validation(stored)

    def validate_bundle(
        self,
        bundle_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        state: HumanValidationState | str = HumanValidationState.ACCEPTED,
    ) -> StoredEvidenceBundle:
        stored = self._bundle(bundle_id)
        if principal.kind is not PrincipalKind.HUMAN:
            raise HumanValidationError("integration principals cannot validate evidence bundles")
        self._require(principal, Action.VIEW_RIGHTS, stored.project_id, acl_epoch)
        parsed = state if isinstance(state, HumanValidationState) else HumanValidationState(str(state))
        if parsed is HumanValidationState.UNREVIEWED:
            raise HumanValidationError("human validation must accept, reject, or request revision")
        record = BundleValidation(
            bundle_id=bundle_id,
            state=parsed,
            actor_id=principal.actor_id,
            created_at=utc_now(),
        )

        def mutate(index: dict[str, Any]) -> BundleValidation:
            validation_id = f"ebv_{new_ulid()}"
            index["validation_ids"] = [*index["validation_ids"], validation_id]
            index["validation_digests"][validation_id] = put_payload(
                self.workspace, record.to_dict()
            )
            index["bundle_validations"][bundle_id] = [
                *index["bundle_validations"].get(bundle_id, []),
                validation_id,
            ]
            return record

        mutate_index(self.workspace, mutate)
        self._audit(
            principal,
            operation="provenance_validate_bundle",
            object_kind="evidence_bundle",
            object_id=bundle_id,
            acl_epoch=acl_epoch,
            reason=parsed.value,
        )
        return self.get_bundle(bundle_id, principal=principal, acl_epoch=acl_epoch)

    def export_disclosure(
        self, bundle_id: str, *, principal: Principal, acl_epoch: int
    ) -> ExportDisclosure:
        stored = self.get_bundle(bundle_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.VIEW_RIGHTS, stored.project_id, acl_epoch)
        source_disclosures: list[dict[str, Any]] = []
        for cited in stored.bundle.cited_sources:
            try:
                disclosure = self.rights.export_source_disclosure(
                    cited.source_id, principal=principal, acl_epoch=acl_epoch
                )
            except Exception as exc:
                raise ExportDisclosureError(
                    f"export failed closed for source {cited.source_id}"
                ) from exc
            source_disclosures.append(disclosure.to_dict())
        packet = ExportDisclosure(
            bundle_id=stored.bundle.id,
            project_id=stored.project_id,
            claim=stored.bundle.claim,
            claim_kind=stored.claim_kind,
            cited_sources=stored.bundle.cited_sources,
            cited_node_ids=stored.bundle.cited_node_ids,
            method_summary=stored.bundle.method_summary,
            method_provenance=stored.method_provenance,
            assumptions=stored.bundle.assumptions,
            confidence=stored.bundle.confidence,
            uncertainty=stored.uncertainty,
            alternatives=stored.bundle.alternatives,
            counter_evidence=stored.bundle.counter_evidence,
            sensitivity=stored.bundle.sensitivity,
            rights_license=stored.rights_license,
            source_disclosures=tuple(source_disclosures),
            lineage=stored.lineage,
            human_validation_state=stored.bundle.human_validation_state,
            validated_by=stored.validated_by,
            validated_at=stored.validated_at,
            epistemic_disclaimer=stored.epistemic_disclaimer,
            exported_at=utc_now(),
            exported_by=principal.actor_id,
        )
        reject_chain_of_thought(packet.to_dict(), field="export_disclosure")

        def mutate(index: dict[str, Any]) -> ExportDisclosure:
            disclosure_id = f"dsc_{new_ulid()}"
            index["disclosure_ids"] = [*index["disclosure_ids"], disclosure_id]
            index["disclosure_digests"][disclosure_id] = put_payload(
                self.workspace, packet.to_dict()
            )
            return packet

        stored_packet = mutate_index(self.workspace, mutate)
        self._audit(
            principal,
            operation="provenance_export_disclosure",
            object_kind="evidence_bundle",
            object_id=bundle_id,
            acl_epoch=acl_epoch,
            reason=stored.claim_kind.value,
        )
        return stored_packet

    def attach_artifact_version(
        self,
        bundle_id: str,
        artifact_version_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> tuple[str, ...]:
        stored = self._bundle(bundle_id)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        if self.artifacts is None:
            raise ExportDisclosureError("artifact service is required to link evidence bundles")
        self.artifacts.get_version(
            artifact_version_id, principal=principal, acl_epoch=acl_epoch
        )

        def mutate(index: dict[str, Any]) -> tuple[str, ...]:
            linked = [
                str(item) for item in index["artifact_links"].get(bundle_id, [])
            ]
            if artifact_version_id not in linked:
                linked.append(artifact_version_id)
            index["artifact_links"][bundle_id] = linked
            return tuple(linked)

        links = mutate_index(self.workspace, mutate)
        self._audit(
            principal,
            operation="provenance_attach_artifact",
            object_kind="evidence_bundle",
            object_id=bundle_id,
            acl_epoch=acl_epoch,
            reason=artifact_version_id,
        )
        return links

    def list_artifact_links(self, bundle_id: str) -> tuple[str, ...]:
        index = load_index(self.workspace)
        if bundle_id not in index["bundle_digests"]:
            raise EvidenceBundleNotFoundError(f"unknown evidence bundle: {bundle_id}")
        return tuple(str(item) for item in index["artifact_links"].get(bundle_id, []))

    def _bundle(self, bundle_id: str) -> StoredEvidenceBundle:
        index = load_index(self.workspace)
        digest = index["bundle_digests"].get(bundle_id)
        if digest is None:
            raise EvidenceBundleNotFoundError(f"unknown evidence bundle: {bundle_id}")
        return StoredEvidenceBundle.from_dict(load_payload(self.workspace, str(digest)))

    def _with_validation(self, stored: StoredEvidenceBundle) -> StoredEvidenceBundle:
        index = load_index(self.workspace)
        validation_ids = index["bundle_validations"].get(stored.bundle.id, [])
        if not validation_ids:
            return stored
        latest = BundleValidation.from_dict(
            load_payload(self.workspace, str(index["validation_digests"][str(validation_ids[-1])]))
        )
        bundle = replace(
            stored.bundle,
            human_validation_state=latest.state,
        )
        validated_by = latest.actor_id if latest.state is HumanValidationState.ACCEPTED else None
        validated_at = latest.created_at if latest.state is HumanValidationState.ACCEPTED else None
        return replace(
            stored,
            bundle=bundle,
            validated_by=validated_by,
            validated_at=validated_at,
        )

    @staticmethod
    def _parse_citation(value: CitationInput | Mapping[str, Any]) -> CitationInput:
        if isinstance(value, CitationInput):
            return value
        return CitationInput(
            source_id=str(value["source_id"]),
            excerpt_summary=str(value.get("excerpt_summary") or ""),
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

    def _audit(
        self,
        principal: Principal,
        *,
        operation: str,
        object_kind: str,
        object_id: str,
        acl_epoch: int,
        reason: str,
    ) -> None:
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=operation,
            object_kind=object_kind,
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )


EvidenceBundleService = ProvenanceService
