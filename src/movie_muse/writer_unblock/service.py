"""Writer-unblock: structurally distinct routes as non-canonical proposals."""

from __future__ import annotations

from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.creative_intent.api import CreativeIntentService, IntentKind
from movie_muse.identity.api import Principal
from movie_muse.model_router.api import ModelRequest, ModelRouter, RoleContract
from movie_muse.persistence.api import utc_now
from movie_muse.proposals.api import ProposalOrigin, ProposalService
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import (
    BlockKind,
    ChangeSet,
    ChangeSetOperation,
    OperationType,
    new_id,
    new_ulid,
)
from movie_muse.writer_unblock.errors import (
    CombineError,
    ConsentRequiredError,
    ExecutorRequiredError,
    HiddenAuthorityError,
    UnknownRouteError,
)
from movie_muse.writer_unblock.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.writer_unblock.types import (
    DivergenceRoute,
    DivergenceSession,
    MetricKind,
    MetricRecord,
    RouteKind,
)

HIDDEN_AUTHORITY = (
    "you should",
    "you must",
    "the correct",
    "the right choice",
    "the only way",
    "obviously the",
    "trust the model",
    "canonically",
)

ROUTE_CATALOG: tuple[tuple[RouteKind, str, str, str], ...] = (
    (
        RouteKind.BEHAVIORAL,
        "Ada pauses before touching the lock.",
        "Ada remains the investigator",
        "Ada's immediate certainty becomes hesitation",
    ),
    (
        RouteKind.POWER_INVERSION,
        "The lock waits for Ada to blink first.",
        "Ada remains present in the beat",
        "agency tilts toward the object for one beat",
    ),
    (
        RouteKind.SILENCE,
        "Ada studies the lock. No one speaks.",
        "the scene still happens",
        "dialogue is withheld",
    ),
    (
        RouteKind.MISDIRECTION,
        "Ada studies the kettle, not the lock.",
        "Ada remains the investigator",
        "attention is pointed at a decoy",
    ),
    (
        RouteKind.VISUAL,
        "Hard sidelight cuts Ada from the lock.",
        "story function of the beat",
        "the image, not the line, carries the cut",
    ),
    (
        RouteKind.STRUCTURAL,
        "The lock beat moves after the next heading.",
        "Ada remains the investigator",
        "order of information changes",
    ),
    (
        RouteKind.PRODUCTION_CONSTRAINED,
        "Ada studies the lock in a single tight coverage setup.",
        "the investigation beat",
        "coverage is constrained to one setup",
    ),
    (
        RouteKind.RADICAL_DELETE,
        "Ada is already past the lock.",
        "Ada remains the investigator later",
        "this beat is offered as optional to cut",
    ),
)


def _new_sid(prefix: str) -> str:
    return f"{prefix}_{new_ulid()}"


def assert_no_hidden_authority(text: str) -> str:
    lowered = text.lower()
    for phrase in HIDDEN_AUTHORITY:
        if phrase in lowered:
            raise HiddenAuthorityError(f"hidden-authority language is not allowed: {phrase}")
    return text


class WriterUnblockService:
    """Produce inspectable divergence routes. Never writes canon itself."""

    def __init__(
        self,
        proposals: ProposalService,
        revisions: RevisionService,
        authorization: AuthorizationService,
        audit: AuditLog,
        router: ModelRouter,
        *,
        creative_intent: CreativeIntentService | None = None,
    ) -> None:
        self.proposals = proposals
        self.revisions = revisions
        self.authorization = authorization
        self.audit = audit
        self.router = router
        self.creative_intent = creative_intent
        self.workspace = revisions.workspace

    def generate_routes(
        self,
        *,
        principal: Principal,
        acl_epoch: int,
        project_id: str,
        rejected_ideas: tuple[str, ...] = (),
        invariants: tuple[str, ...] = (),
        permission_snapshot_id: str,
    ) -> DivergenceSession:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        head = self.revisions.canon_branch().head_revision_id
        declared = self._invariants(invariants)
        rejected = tuple(item.strip() for item in rejected_ideas if item.strip())
        decision_id = self._propose_alternatives(
            principal=principal,
            acl_epoch=acl_epoch,
            project_id=project_id,
            snapshot=permission_snapshot_id,
            head=head,
        )
        action_id = self._action_id()
        routes: list[DivergenceRoute] = []
        for kind, text, preserved, changed in ROUTE_CATALOG:
            if self._echoes_rejected(text, rejected):
                continue
            candidate = assert_no_hidden_authority(text)
            preserved_tuple = (preserved, *declared)
            branch = self.revisions.create_branch(
                f"unblock-{kind.value}-{new_ulid().lower()}",
                actor_id=principal.actor_id,
            )
            change = ChangeSet(
                id=new_id("change_set"),
                base_revision_id=head,
                author_actor_id=principal.actor_id,
                created_at=utc_now(),
                operations=(
                    ChangeSetOperation(
                        id="cop_0",
                        order=0,
                        op_type=OperationType.UPDATE_BLOCK,
                        target_id=action_id,
                        payload={"text": candidate},
                    ),
                ),
            )
            envelope = self.proposals.submit(
                change,
                principal=principal,
                acl_epoch=acl_epoch,
                project_id=project_id,
                intent=f"divergence:{kind.value}",
                rationale_summary=changed,
                provenance="ai:propose_alternatives",
                origin=ProposalOrigin.AI,
            )
            routes.append(
                DivergenceRoute(
                    id=_new_sid("rte"),
                    kind=kind,
                    preserved=preserved_tuple,
                    changed=(changed,),
                    rationale=(
                        f"Candidate {kind.value} route. It does not claim a correct "
                        "choice; the writer decides whether to keep, combine, or reject it."
                    ),
                    candidate_text=candidate,
                    proposal_id=envelope.proposal.id,
                    branch_id=branch.id,
                    provenance_id=decision_id,
                )
            )
        session = DivergenceSession(
            id=_new_sid("wub"),
            project_id=project_id,
            base_revision_id=head,
            routes=tuple(routes),
            rejected_ideas=rejected,
            invariants=declared,
            model_decision_id=decision_id,
        )
        self._put_session(session)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="writer_unblock.generate_routes",
            object_kind="writer_unblock_session",
            object_id=session.id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason="generated non-canonical divergence routes",
            before_revision_id=head,
        )
        return session

    def generate_prose(
        self,
        session_id: str,
        route_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        permission_snapshot_id: str,
        executor_mode: bool,
    ) -> DivergenceRoute:
        if not executor_mode:
            raise ExecutorRequiredError("explicit Executor mode is required for prose generation")
        session = self._session(session_id)
        self._require(principal, Action.PROPOSE, session.project_id, acl_epoch)
        route = self._route(session, route_id)
        request = ModelRequest(
            capability="generate_text",
            data_classification="internal",
            latency_budget_ms=5000,
            cost_budget=5.0,
            offline_required=False,
            context_tokens=128,
            structured_output=True,
            quality_tier="fast",
            role_contract=RoleContract.EXECUTOR.value,
            project_id=session.project_id,
            actor_id=principal.actor_id,
            acl_epoch=acl_epoch,
            permission_snapshot_id=permission_snapshot_id,
            input={"text": route.candidate_text, "kind": route.kind.value},
            consent_granted=True,
        )
        quote = self.router.quote(request)
        result = self.router.execute(request, quote_id=quote.id)
        prose = assert_no_hidden_authority(str(result.output.get("text") or ""))
        updated = DivergenceRoute(
            id=route.id,
            kind=route.kind,
            preserved=route.preserved,
            changed=route.changed,
            rationale=route.rationale,
            candidate_text=route.candidate_text,
            proposal_id=route.proposal_id,
            branch_id=route.branch_id,
            prose=prose,
            provenance_id=result.decision.id,
        )
        self._replace_route(session, updated)
        return updated

    def combine(
        self,
        session_id: str,
        route_ids: tuple[str, ...],
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> DivergenceRoute:
        if len(route_ids) < 2:
            raise CombineError("combine requires at least two routes")
        session = self._session(session_id)
        self._require(principal, Action.PROPOSE, session.project_id, acl_epoch)
        selected = tuple(self._route(session, item) for item in route_ids)
        combined_text = " ".join(item.candidate_text.rstrip(".") for item in selected) + "."
        candidate = assert_no_hidden_authority(combined_text)
        head = session.base_revision_id
        branch = self.revisions.create_branch(
            f"unblock-combine-{new_ulid().lower()}",
            actor_id=principal.actor_id,
        )
        change = ChangeSet(
            id=new_id("change_set"),
            base_revision_id=head,
            author_actor_id=principal.actor_id,
            created_at=utc_now(),
            operations=(
                ChangeSetOperation(
                    id="cop_0",
                    order=0,
                    op_type=OperationType.UPDATE_BLOCK,
                    target_id=self._action_id(),
                    payload={"text": candidate},
                ),
            ),
        )
        envelope = self.proposals.submit(
            change,
            principal=principal,
            acl_epoch=acl_epoch,
            project_id=session.project_id,
            intent="divergence:combine",
            rationale_summary="writer-combined routes",
            provenance="human-author",
            origin=ProposalOrigin.HUMAN,
        )
        combined = DivergenceRoute(
            id=_new_sid("rte"),
            kind=RouteKind.STRUCTURAL,
            preserved=session.invariants,
            changed=tuple(item.kind.value for item in selected),
            rationale="Writer-combined candidate. No route is treated as the correct answer.",
            candidate_text=candidate,
            proposal_id=envelope.proposal.id,
            branch_id=branch.id,
        )
        updated = DivergenceSession(
            id=session.id,
            project_id=session.project_id,
            base_revision_id=session.base_revision_id,
            routes=(*session.routes, combined),
            rejected_ideas=session.rejected_ideas,
            invariants=session.invariants,
            model_decision_id=session.model_decision_id,
        )
        self._put_session(updated)
        return combined

    def edit(
        self,
        session_id: str,
        route_id: str,
        text: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> DivergenceRoute:
        session = self._session(session_id)
        self._require(principal, Action.PROPOSE, session.project_id, acl_epoch)
        route = self._route(session, route_id)
        candidate = assert_no_hidden_authority(text)
        change = ChangeSet(
            id=new_id("change_set"),
            base_revision_id=session.base_revision_id,
            author_actor_id=principal.actor_id,
            created_at=utc_now(),
            operations=(
                ChangeSetOperation(
                    id="cop_0",
                    order=0,
                    op_type=OperationType.UPDATE_BLOCK,
                    target_id=self._action_id(),
                    payload={"text": candidate},
                ),
            ),
        )
        envelope = self.proposals.submit(
            change,
            principal=principal,
            acl_epoch=acl_epoch,
            project_id=session.project_id,
            intent=f"divergence:edit:{route.kind.value}",
            rationale_summary="writer-edited candidate",
            provenance="human-author",
            origin=ProposalOrigin.HUMAN,
        )
        edited = DivergenceRoute(
            id=route.id,
            kind=route.kind,
            preserved=route.preserved,
            changed=route.changed,
            rationale=route.rationale,
            candidate_text=candidate,
            proposal_id=envelope.proposal.id,
            branch_id=route.branch_id,
            prose=route.prose,
            provenance_id=route.provenance_id,
        )
        self._replace_route(session, edited)
        return edited

    def reject(
        self,
        session_id: str,
        route_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> DivergenceRoute:
        session = self._session(session_id)
        route = self._route(session, route_id)
        self.proposals.reject(
            route.proposal_id,
            principal=principal,
            acl_epoch=acl_epoch,
        )
        return route

    def record_metric(
        self,
        session_id: str,
        *,
        kind: MetricKind | str,
        target_id: str,
        consent: bool,
        payload: dict[str, Any] | None = None,
    ) -> MetricRecord:
        if not consent:
            raise ConsentRequiredError("suggestion metrics require explicit consent")
        session = self._session(session_id)
        parsed = MetricKind(kind)
        record = MetricRecord(
            id=_new_sid("wum"),
            kind=parsed,
            session_id=session.id,
            target_id=target_id,
            consent_granted=True,
            training_eligible=False,
            payload=dict(payload or {}),
        )

        def persist(index: dict[str, Any]) -> None:
            metrics = list(index["metrics"])
            metrics.append(record.to_dict())
            index["metrics"] = metrics

        mutate_index(self.workspace, persist)
        return record

    def list_metrics(self, session_id: str) -> tuple[MetricRecord, ...]:
        index = load_index(self.workspace)
        return tuple(
            MetricRecord.from_dict(item)
            for item in index["metrics"]
            if str(item.get("session_id")) == session_id
        )

    def get_session(self, session_id: str) -> DivergenceSession:
        return self._session(session_id)

    def _propose_alternatives(
        self,
        *,
        principal: Principal,
        acl_epoch: int,
        project_id: str,
        snapshot: str,
        head: str,
    ) -> str:
        request = ModelRequest(
            capability="propose_alternatives",
            data_classification="internal",
            latency_budget_ms=5000,
            cost_budget=5.0,
            offline_required=False,
            context_tokens=128,
            structured_output=True,
            quality_tier="fast",
            role_contract=RoleContract.DIVERGENCE.value,
            project_id=project_id,
            actor_id=principal.actor_id,
            acl_epoch=acl_epoch,
            permission_snapshot_id=snapshot,
            input={"revision_id": head},
            consent_granted=True,
        )
        quote = self.router.quote(request)
        result = self.router.execute(request, quote_id=quote.id)
        return result.decision.id

    def _invariants(self, extra: tuple[str, ...]) -> tuple[str, ...]:
        found: list[str] = [item.strip() for item in extra if item.strip()]
        if self.creative_intent is None:
            return tuple(found)
        branch_id = self.revisions.canon_branch().id
        for record in self.creative_intent.list(branch_id, stated_only=True):
            if record.envelope.kind in {
                IntentKind.CHARACTER_INVARIANT,
                IntentKind.PLOT_INVARIANT,
            }:
                found.append(record.envelope.intent.statement)
        return tuple(found)

    def _echoes_rejected(self, text: str, rejected: tuple[str, ...]) -> bool:
        lowered = text.lower()
        return any(item.lower() in lowered for item in rejected)

    def _action_id(self) -> str:
        document = self.revisions.replay_head()
        return next(block.id for block in document.blocks if block.kind is BlockKind.ACTION)

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )

    def _session(self, session_id: str) -> DivergenceSession:
        index = load_index(self.workspace)
        digest = index["digests"].get(session_id)
        if digest is None:
            raise UnknownRouteError(f"unknown session: {session_id}")
        return DivergenceSession.from_dict(load_payload(self.workspace, str(digest)))

    def _route(self, session: DivergenceSession, route_id: str) -> DivergenceRoute:
        try:
            return session.route(route_id)
        except KeyError as exc:
            raise UnknownRouteError(f"unknown route: {route_id}") from exc

    def _replace_route(self, session: DivergenceSession, route: DivergenceRoute) -> None:
        routes = tuple(route if item.id == route.id else item for item in session.routes)
        updated = DivergenceSession(
            id=session.id,
            project_id=session.project_id,
            base_revision_id=session.base_revision_id,
            routes=routes,
            rejected_ideas=session.rejected_ideas,
            invariants=session.invariants,
            model_decision_id=session.model_decision_id,
        )
        self._put_session(updated)

    def _put_session(self, session: DivergenceSession) -> None:
        def persist(index: dict[str, Any]) -> None:
            digest = put_payload(self.workspace, session.to_dict())
            digests = dict(index["digests"])
            digests[session.id] = digest
            index["digests"] = digests
            if session.id not in list(index["session_ids"]):
                index["session_ids"] = [*list(index["session_ids"]), session.id]

        mutate_index(self.workspace, persist)