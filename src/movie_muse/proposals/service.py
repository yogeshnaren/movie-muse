"""Inspectable proposals. AI may propose; only humans can write canon."""

from __future__ import annotations

from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.dependencies.api import DependencyEngine
from movie_muse.identity.api import Principal, PrincipalKind
from movie_muse.persistence.api import utc_now
from movie_muse.proposals.errors import (
    DirectCanonWriteError,
    PartialAcceptError,
    ProposalStateError,
    UnknownProposalError,
)
from movie_muse.proposals.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.proposals.types import (
    AcceptResult,
    ProposalEnvelope,
    ProposalOrigin,
    ProposalReview,
)
from movie_muse.revisions.api import RevisionService, StaleProposalError
from movie_muse.schemas.api import (
    ChangeSet,
    ChangeSetOperation,
    ImpactSummary,
    Proposal,
    ProposalStatus,
    new_id,
)


class ProposalService:
    """Lifecycle for inspectable ChangeSet proposals. No model calls."""

    def __init__(
        self,
        revisions: RevisionService,
        authorization: AuthorizationService,
        audit: AuditLog,
        graph: DependencyEngine | None = None,
    ) -> None:
        self.revisions = revisions
        self.authorization = authorization
        self.audit = audit
        self.graph = graph
        self.workspace = revisions.workspace

    def submit(
        self,
        change_set: ChangeSet,
        *,
        principal: Principal,
        acl_epoch: int,
        project_id: str,
        intent: str,
        rationale_summary: str,
        provenance: str,
        origin: ProposalOrigin | str = ProposalOrigin.HUMAN,
        impact: ImpactSummary | None = None,
        alternatives: tuple[ChangeSet, ...] = (),
        evidence_ids: tuple[str, ...] = (),
        remainder_of: str | None = None,
        accepted_operation_ids: tuple[str, ...] | None = None,
    ) -> ProposalEnvelope:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        if change_set.author_actor_id != principal.actor_id:
            raise ProposalStateError("change set author must match the proposing principal")
        proposal = Proposal(
            id=new_id("proposal"),
            project_id=project_id,
            change_set=change_set,
            base_revision_id=change_set.base_revision_id,
            intent=intent,
            rationale_summary=rationale_summary,
            provenance=provenance,
            created_at=utc_now(),
            status=ProposalStatus.PENDING,
            impact=impact or ImpactSummary(),
        )
        stored = self.revisions.store_proposal(proposal)
        envelope = ProposalEnvelope(
            proposal=stored,
            origin=ProposalOrigin(origin),
            alternative_change_sets=alternatives,
            evidence_ids=evidence_ids,
            remainder_of=remainder_of,
            accepted_operation_ids=accepted_operation_ids,
        )
        self._put_envelope(envelope)
        return envelope

    def review(self, proposal_id: str, *, branch_ref: str | None = None) -> ProposalReview:
        envelope = self._envelope(proposal_id)
        head = self.revisions.get_branch(
            branch_ref or self.revisions.canon_branch().id
        ).head_revision_id
        proposal = self.revisions.get_proposal(proposal_id)
        live = ProposalEnvelope(
            proposal=proposal,
            origin=envelope.origin,
            alternative_change_sets=envelope.alternative_change_sets,
            evidence_ids=envelope.evidence_ids,
            remainder_of=envelope.remainder_of,
            accepted_operation_ids=envelope.accepted_operation_ids,
        )
        return ProposalReview(
            envelope=live,
            stale=proposal.base_revision_id != head and proposal.status is ProposalStatus.PENDING,
            head_revision_id=head,
        )

    def accept(
        self,
        proposal_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        branch_ref: str | None = None,
    ) -> AcceptResult:
        self._assert_human_canon(principal)
        envelope = self._envelope(proposal_id)
        self._require(principal, Action.ACCEPT, envelope.proposal.project_id, acl_epoch)
        review = self.review(proposal_id, branch_ref=branch_ref)
        if review.stale:
            raise StaleProposalError(
                "proposal base_revision_id is not the current branch head; fail closed"
            )
        before = review.head_revision_id
        accepted, ack = self.revisions.accept_proposal(
            proposal_id, actor_id=principal.actor_id, branch_ref=branch_ref
        )
        invalidated = self._invalidate(
            accepted.change_set,
            ack.revision_id,
            principal,
            acl_epoch,
            project_id=accepted.project_id,
        )
        audit = self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="proposal.accept",
            object_kind="proposal",
            object_id=proposal_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason="accepted inspectable proposal into canon",
            before_revision_id=before,
            after_revision_id=ack.revision_id,
        )
        return AcceptResult(
            proposal=accepted,
            revision_id=ack.revision_id,
            audit_id=audit.id,
            invalidated_node_ids=invalidated,
        )

    def accept_partial(
        self,
        proposal_id: str,
        operation_ids: tuple[str, ...],
        *,
        principal: Principal,
        acl_epoch: int,
        branch_ref: str | None = None,
    ) -> AcceptResult:
        if not operation_ids:
            raise PartialAcceptError("partial acceptance must name at least one operation")
        self._assert_human_canon(principal)
        envelope = self._envelope(proposal_id)
        self._require(principal, Action.ACCEPT, envelope.proposal.project_id, acl_epoch)
        proposal = self.revisions.get_proposal(proposal_id)
        if proposal.status is not ProposalStatus.PENDING:
            raise ProposalStateError("only pending proposals can be partially accepted")
        by_id = {op.id: op for op in proposal.change_set.operations}
        missing = [item for item in operation_ids if item not in by_id]
        if missing:
            raise PartialAcceptError(f"unknown operations: {', '.join(missing)}")
        selected = tuple(by_id[item] for item in operation_ids)
        leftover = tuple(op for op in proposal.change_set.operations if op.id not in set(operation_ids))
        subset = ChangeSet(
            id=new_id("change_set"),
            base_revision_id=proposal.base_revision_id,
            author_actor_id=principal.actor_id,
            created_at=utc_now(),
            operations=tuple(
                ChangeSetOperation(
                    id=op.id,
                    order=index,
                    op_type=op.op_type,
                    target_id=op.target_id,
                    payload=dict(op.payload),
                )
                for index, op in enumerate(selected)
            ),
        )
        subset_env = self.submit(
            subset,
            principal=principal,
            acl_epoch=acl_epoch,
            project_id=proposal.project_id,
            intent=proposal.intent,
            rationale_summary=f"partial accept of {proposal.id}",
            provenance=proposal.provenance,
            origin=envelope.origin,
            impact=proposal.impact,
            evidence_ids=envelope.evidence_ids,
            accepted_operation_ids=operation_ids,
        )
        result = self.accept(subset_env.proposal.id, principal=principal, acl_epoch=acl_epoch, branch_ref=branch_ref)
        remainder: Proposal | None = None
        if leftover:
            remainder_cs = ChangeSet(
                id=new_id("change_set"),
                base_revision_id=result.revision_id,
                author_actor_id=principal.actor_id,
                created_at=utc_now(),
                operations=tuple(
                    ChangeSetOperation(
                        id=op.id,
                        order=index,
                        op_type=op.op_type,
                        target_id=op.target_id,
                        payload=dict(op.payload),
                    )
                    for index, op in enumerate(leftover)
                ),
            )
            remainder_env = self.submit(
                remainder_cs,
                principal=principal,
                acl_epoch=acl_epoch,
                project_id=proposal.project_id,
                intent=proposal.intent,
                rationale_summary=f"remainder after partial accept of {proposal.id}",
                provenance=proposal.provenance,
                origin=envelope.origin,
                impact=proposal.impact,
                evidence_ids=envelope.evidence_ids,
                remainder_of=proposal.id,
            )
            remainder = remainder_env.proposal
        self.revisions.reject_proposal(proposal_id, actor_id=principal.actor_id)
        return AcceptResult(
            proposal=result.proposal,
            revision_id=result.revision_id,
            audit_id=result.audit_id,
            remainder=remainder,
            invalidated_node_ids=result.invalidated_node_ids,
        )

    def reject(
        self,
        proposal_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> Proposal:
        envelope = self._envelope(proposal_id)
        self._require(principal, Action.ACCEPT, envelope.proposal.project_id, acl_epoch)
        rejected = self.revisions.reject_proposal(proposal_id, actor_id=principal.actor_id)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="proposal.reject",
            object_kind="proposal",
            object_id=proposal_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason="rejected inspectable proposal",
            before_revision_id=rejected.base_revision_id,
        )
        return rejected

    def rebase(
        self,
        proposal_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        branch_ref: str | None = None,
    ) -> ProposalEnvelope:
        envelope = self._envelope(proposal_id)
        self._require(principal, Action.PROPOSE, envelope.proposal.project_id, acl_epoch)
        rebased = self.revisions.rebase_proposal(
            proposal_id, actor_id=principal.actor_id, branch_ref=branch_ref
        )
        new_envelope = ProposalEnvelope(
            proposal=rebased,
            origin=envelope.origin,
            alternative_change_sets=envelope.alternative_change_sets,
            evidence_ids=envelope.evidence_ids,
        )
        self._put_envelope(new_envelope)
        return new_envelope

    def accept_alternative(
        self,
        proposal_id: str,
        alternative_index: int,
        *,
        principal: Principal,
        acl_epoch: int,
        branch_ref: str | None = None,
    ) -> AcceptResult:
        self._assert_human_canon(principal)
        envelope = self._envelope(proposal_id)
        if alternative_index < 0 or alternative_index >= len(envelope.alternative_change_sets):
            raise PartialAcceptError("unknown alternative index")
        chosen = envelope.alternative_change_sets[alternative_index]
        retargeted = ChangeSet(
            id=new_id("change_set"),
            base_revision_id=chosen.base_revision_id,
            author_actor_id=principal.actor_id,
            created_at=utc_now(),
            operations=tuple(
                ChangeSetOperation(
                    id=op.id,
                    order=index,
                    op_type=op.op_type,
                    target_id=op.target_id,
                    payload=dict(op.payload),
                )
                for index, op in enumerate(chosen.operations)
            ),
        )
        submitted = self.submit(
            retargeted,
            principal=principal,
            acl_epoch=acl_epoch,
            project_id=envelope.proposal.project_id,
            intent=envelope.proposal.intent,
            rationale_summary=f"accepted alternative {alternative_index} of {proposal_id}",
            provenance=envelope.proposal.provenance,
            origin=envelope.origin,
            impact=envelope.proposal.impact,
            evidence_ids=envelope.evidence_ids,
        )
        result = self.accept(
            submitted.proposal.id, principal=principal, acl_epoch=acl_epoch, branch_ref=branch_ref
        )
        self.revisions.reject_proposal(proposal_id, actor_id=principal.actor_id)
        return result

    def list(self) -> tuple[ProposalReview, ...]:
        return tuple(self.review(item.id) for item in self.revisions.list_proposals())

    def _invalidate(
        self,
        change_set: ChangeSet,
        revision_id: str,
        principal: Principal,
        acl_epoch: int,
        project_id: str | None = None,
    ) -> tuple[str, ...]:
        if self.graph is None:
            return ()
        result = self.graph.invalidate_for_change_set(
            change_set,
            result_revision_id=revision_id,
            principal=principal,
            acl_epoch=acl_epoch,
            project_id=project_id,
        )
        return tuple(result.closure)

    def _assert_human_canon(self, principal: Principal) -> None:
        if principal.kind is not PrincipalKind.HUMAN:
            raise DirectCanonWriteError("AI cannot directly write canon; submit a proposal")

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )

    def _envelope(self, proposal_id: str) -> ProposalEnvelope:
        index = load_index(self.workspace)
        digest = index["digests"].get(proposal_id)
        if digest is None:
            raise UnknownProposalError(f"unknown proposal: {proposal_id}")
        return ProposalEnvelope.from_dict(load_payload(self.workspace, str(digest)))

    def _put_envelope(self, envelope: ProposalEnvelope) -> None:
        def persist(index: dict[str, Any]) -> None:
            digest = put_payload(self.workspace, envelope.to_dict())
            digests = dict(index["digests"])
            digests[envelope.proposal.id] = digest
            index["digests"] = digests
            if envelope.proposal.id not in list(index["ids"]):
                index["ids"] = [*list(index["ids"]), envelope.proposal.id]

        mutate_index(self.workspace, persist)
