"""Role-filtered department views, craft-owner actions, notices, and assignments."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import (
    Action,
    AuthContext,
    AuthorizationService,
    ResourceKind,
)
from movie_muse.breakdown.api import BreakdownElement, BreakdownService, StoredBreakdown
from movie_muse.department_handoff.errors import (
    DepartmentDeniedError,
    NoticeNotFoundError,
    PacketNotFoundError,
)
from movie_muse.department_handoff.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.department_handoff.mapping import department_for, kinds_for
from movie_muse.department_handoff.types import (
    Assignment,
    ChangeNotice,
    CraftAction,
    CraftDecision,
    DepartmentPacket,
)
from movie_muse.identity.api import IdentityService, Principal, PrincipalKind, Role
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import (
    ProjectEvent,
    compute_integrity_hash,
    new_id,
    new_ulid,
    to_json_dict,
)

T = TypeVar("T")

_CROSS_DEPARTMENT_ROLES = frozenset(
    {Role.OWNER, Role.ADMINISTRATOR, Role.DIRECTOR, Role.PRODUCER}
)
_CRAFT_CONFIRM_ACTIONS = frozenset(
    {
        CraftAction.CONFIRM,
        CraftAction.CORRECT,
        CraftAction.ADD_ASSUMPTION,
        CraftAction.NOT_APPLICABLE,
    }
)
_EVENT_FOR_ACTION = {
    CraftAction.CONFIRM: "DepartmentDecisionConfirmed",
    CraftAction.CORRECT: "DepartmentDecisionConfirmed",
    CraftAction.ADD_ASSUMPTION: "AssumptionChanged",
    CraftAction.NOT_APPLICABLE: "ProductionRequirementConfirmed",
    CraftAction.ASK_DIRECTOR: "ProductionRequirementConfirmed",
}


class DepartmentHandoffService:
    """Department packets over breakdown elements. Craft confirmations emit ProjectEvents."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        identity: IdentityService,
        revisions: RevisionService,
        breakdown: BreakdownService,
        *,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.identity = identity
        self.revisions = revisions
        self.breakdown = breakdown
        self.clock = clock

    def department_view(
        self,
        breakdown_id: str,
        department: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> DepartmentPacket:
        stored = self.breakdown.get_breakdown(
            breakdown_id, principal=principal, acl_epoch=acl_epoch
        )
        self._require(principal, Action.READ, stored.projection.project_id, acl_epoch)
        self._assert_department_visible(principal, stored.projection.project_id, department)
        return self._packet_for(stored, department)

    def craft_action(
        self,
        breakdown_id: str,
        element_id: str,
        action: CraftAction | str,
        *,
        principal: Principal,
        acl_epoch: int,
        note: str = "",
    ) -> CraftDecision:
        if principal.kind is not PrincipalKind.HUMAN:
            raise DepartmentDeniedError("only a human craft owner may record department decisions")
        parsed = action if isinstance(action, CraftAction) else CraftAction(str(action))
        stored = self.breakdown.get_breakdown(
            breakdown_id, principal=principal, acl_epoch=acl_epoch
        )
        element = self._element(stored, element_id)
        department = department_for(element.kind)
        project_id = stored.projection.project_id
        self._assert_department_visible(principal, project_id, department)
        decision_id = f"dec_{new_ulid()}"
        if parsed in _CRAFT_CONFIRM_ACTIONS:
            self.authorization.declare_operation(
                project_id=project_id,
                operation_id=decision_id,
                department=department,
            )
            self.authorization.require(
                principal,
                Action.CONFIRM_CRAFT_DECISION,
                self.authorization.resource_for_project(
                    project_id,
                    kind=ResourceKind.OPERATION,
                    resource_id=decision_id,
                    department=department,
                ),
                acl_epoch=acl_epoch,
                context=AuthContext(department=department),
            )
        else:
            self._require(principal, Action.COMMENT, project_id, acl_epoch)
        event = self._emit_event(
            project_id=project_id,
            actor_id=principal.actor_id,
            event_type=_EVENT_FOR_ACTION[parsed],
            payload={
                "decision_id": decision_id,
                "element_id": element.id,
                "department": department,
                "action": parsed.value,
                "note": note,
            },
        )
        decision = CraftDecision(
            id=decision_id,
            project_id=project_id,
            breakdown_id=stored.projection.id,
            element_id=element.id,
            department=department,
            action=parsed,
            actor_id=principal.actor_id,
            note=note,
            created_at=self.clock(),
            event_id=event.id,
        )
        stored_decision = self._put_keyed(
            decision.to_dict(),
            item_id=decision.id,
            ids_key="decision_ids",
            digests_key="decision_digests",
            project_id=project_id,
            restore=CraftDecision.from_dict,
        )
        self._audit(
            principal, acl_epoch, "handoff.craft_action", stored_decision.id, parsed.value
        )
        return stored_decision

    def notify_screenplay_changed(
        self,
        breakdown_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
        scene_ids: Sequence[str] = (),
    ) -> tuple[ChangeNotice, ...]:
        stored = self.breakdown.get_breakdown(
            breakdown_id, principal=principal, acl_epoch=acl_epoch
        )
        project_id = stored.projection.project_id
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        wanted = set(scene_ids)
        affected: dict[str, list[str]] = {}
        for element in stored.elements:
            if wanted and not any(item.scene_id in wanted for item in element.evidence):
                continue
            department = department_for(element.kind)
            affected.setdefault(department, []).append(element.id)
        notices: list[ChangeNotice] = []
        for department, element_ids in sorted(affected.items()):
            notice = ChangeNotice(
                id=f"ntc_{new_ulid()}",
                project_id=project_id,
                breakdown_id=stored.projection.id,
                department=department,
                source_revision_id=stored.locked_revision_id,
                element_ids=tuple(element_ids),
                created_at=self.clock(),
                created_by_actor_id=principal.actor_id,
            )
            notices.append(
                self._put_keyed(
                    notice.to_dict(),
                    item_id=notice.id,
                    ids_key="notice_ids",
                    digests_key="notice_digests",
                    project_id=project_id,
                    restore=ChangeNotice.from_dict,
                )
            )
        self._audit(
            principal,
            acl_epoch,
            "handoff.notify_screenplay_changed",
            stored.projection.id,
            ",".join(notice.department for notice in notices),
        )
        return tuple(notices)

    def acknowledge_notice(
        self,
        notice_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> ChangeNotice:
        notice = self._load_notice(notice_id)
        self._assert_department_visible(principal, notice.project_id, notice.department)
        self._require(principal, Action.COMMENT, notice.project_id, acl_epoch)
        updated = ChangeNotice(
            id=notice.id,
            project_id=notice.project_id,
            breakdown_id=notice.breakdown_id,
            department=notice.department,
            source_revision_id=notice.source_revision_id,
            element_ids=notice.element_ids,
            created_at=notice.created_at,
            created_by_actor_id=notice.created_by_actor_id,
            acknowledged_by_actor_id=principal.actor_id,
        )
        stored = self._put_keyed(
            updated.to_dict(),
            item_id=updated.id,
            ids_key="notice_ids",
            digests_key="notice_digests",
            project_id=updated.project_id,
            restore=ChangeNotice.from_dict,
        )
        self._audit(principal, acl_epoch, "handoff.acknowledge", stored.id, stored.department)
        return stored

    def assign(
        self,
        breakdown_id: str,
        element_id: str,
        *,
        assignee_actor_id: str,
        principal: Principal,
        acl_epoch: int,
    ) -> Assignment:
        stored = self.breakdown.get_breakdown(
            breakdown_id, principal=principal, acl_epoch=acl_epoch
        )
        self._require(principal, Action.PROPOSE, stored.projection.project_id, acl_epoch)
        membership = self.identity.accepted_membership_for(
            principal.actor_id, project_id=stored.projection.project_id
        )
        if membership is None or membership.role not in _CROSS_DEPARTMENT_ROLES:
            raise DepartmentDeniedError("only a cross-department role may assign craft owners")
        element = self._element(stored, element_id)
        assignment = Assignment(
            id=f"asg_{new_ulid()}",
            project_id=stored.projection.project_id,
            breakdown_id=stored.projection.id,
            element_id=element.id,
            department=department_for(element.kind),
            assignee_actor_id=assignee_actor_id,
            created_at=self.clock(),
            created_by_actor_id=principal.actor_id,
        )
        written = self._put_keyed(
            assignment.to_dict(),
            item_id=assignment.id,
            ids_key="assignment_ids",
            digests_key="assignment_digests",
            project_id=assignment.project_id,
            restore=Assignment.from_dict,
        )
        self._audit(principal, acl_epoch, "handoff.assign", written.id, written.department)
        return written

    def export_packet(
        self,
        breakdown_id: str,
        department: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> str:
        packet = self.department_view(
            breakdown_id, department, principal=principal, acl_epoch=acl_epoch
        )
        self._require(principal, Action.EXPORT, packet.project_id, acl_epoch)
        lines = [
            f"DEPARTMENT {packet.department}",
            f"BREAKDOWN {packet.breakdown_id}",
            f"REVISION {packet.source_revision_id}",
        ]
        for element in packet.elements:
            lines.append(f"{element.kind.value}\t{element.name}\t{element.id}")
        self._audit(principal, acl_epoch, "handoff.export", packet.id, department)
        return "\n".join(lines)

    def list_events(
        self, project_id: str, *, principal: Principal, acl_epoch: int
    ) -> tuple[ProjectEvent, ...]:
        self._require(principal, Action.READ, project_id, acl_epoch)
        index = load_index(self.workspace)
        events: list[ProjectEvent] = []
        for event_id in index.get("event_ids", ()):
            digest = dict(index.get("event_digests", {})).get(str(event_id))
            if digest is None:
                continue
            event = ProjectEvent.from_dict(load_payload(self.workspace, str(digest)))
            if event.project_id == project_id:
                events.append(event)
        return tuple(events)

    def _packet_for(self, stored: StoredBreakdown, department: str) -> DepartmentPacket:
        allowed = kinds_for(department)
        elements = tuple(item for item in stored.elements if item.kind in allowed)
        index = load_index(self.workspace)
        decisions = self._load_many(
            index, "decision_ids", "decision_digests", CraftDecision.from_dict
        )
        notices = self._load_many(index, "notice_ids", "notice_digests", ChangeNotice.from_dict)
        assignments = self._load_many(
            index, "assignment_ids", "assignment_digests", Assignment.from_dict
        )
        packet = DepartmentPacket(
            id=f"hof_{new_ulid()}",
            project_id=stored.projection.project_id,
            breakdown_id=stored.projection.id,
            department=department,
            source_revision_id=stored.locked_revision_id,
            elements=elements,
            decisions=tuple(
                item
                for item in decisions
                if item.breakdown_id == stored.projection.id and item.department == department
            ),
            notices=tuple(
                item
                for item in notices
                if item.breakdown_id == stored.projection.id and item.department == department
            ),
            assignments=tuple(
                item
                for item in assignments
                if item.breakdown_id == stored.projection.id and item.department == department
            ),
            created_at=self.clock(),
        )
        return self._put_keyed(
            packet.to_dict(),
            item_id=packet.id,
            ids_key="packet_ids",
            digests_key="packet_digests",
            project_id=packet.project_id,
            restore=DepartmentPacket.from_dict,
        )

    def _load_many(
        self,
        index: dict[str, Any],
        ids_key: str,
        digests_key: str,
        restore: Callable[[dict[str, Any]], T],
    ) -> tuple[T, ...]:
        items: list[T] = []
        for item_id in index.get(ids_key, ()):
            digest = dict(index.get(digests_key, {})).get(str(item_id))
            if digest is None:
                continue
            items.append(restore(load_payload(self.workspace, str(digest))))
        return tuple(items)

    def _element(self, stored: StoredBreakdown, element_id: str) -> BreakdownElement:
        for element in stored.elements:
            if element.id == element_id:
                return element
        raise PacketNotFoundError(f"element {element_id} is not on breakdown {stored.projection.id}")

    def _load_notice(self, notice_id: str) -> ChangeNotice:
        index = load_index(self.workspace)
        digest = dict(index.get("notice_digests", {})).get(notice_id)
        if digest is None:
            raise NoticeNotFoundError(f"notice {notice_id} is not in the index")
        return ChangeNotice.from_dict(load_payload(self.workspace, str(digest)))

    def _assert_department_visible(
        self, principal: Principal, project_id: str, department: str
    ) -> None:
        membership = self.identity.accepted_membership_for(
            principal.actor_id, project_id=project_id
        )
        if membership is None:
            raise DepartmentDeniedError("no accepted membership on this project")
        if membership.role in _CROSS_DEPARTMENT_ROLES:
            return
        if (
            membership.role is Role.DEPARTMENT_CONTRIBUTOR
            and membership.department == department
        ):
            return
        raise DepartmentDeniedError(
            f"principal cannot access department {department}"
        )

    def _emit_event(
        self,
        *,
        project_id: str,
        actor_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> ProjectEvent:
        branch = self.revisions.canon_branch()
        command = new_ulid()
        operation = new_ulid()
        payload_dict = to_json_dict(payload) if payload else {}
        if not isinstance(payload_dict, dict):
            raise TypeError("event payload must serialize to an object")
        integrity_hash = compute_integrity_hash(
            project_id=project_id,
            branch_id=branch.id,
            base_revision_id=branch.head_revision_id,
            result_revision_id=branch.head_revision_id,
            actor_id=actor_id,
            effective_principal_id=actor_id,
            command_id=command,
            operation_id=operation,
            event_type=event_type,
            schema_version="1.0",
            causal_id=None,
            correlation_id=command,
            payload=payload_dict,
        )
        event = ProjectEvent(
            id=new_id("event"),
            project_id=project_id,
            branch_id=branch.id,
            result_revision_id=branch.head_revision_id,
            actor_id=actor_id,
            effective_principal_id=actor_id,
            command_id=command,
            operation_id=operation,
            event_type=event_type,
            created_at=self.clock(),
            correlation_id=command,
            integrity_hash=integrity_hash,
            base_revision_id=branch.head_revision_id,
            payload=payload_dict,
        )

        def persist(index: dict[str, Any]) -> ProjectEvent:
            digest = put_payload(self.workspace, event.to_dict())
            ids = list(index.get("event_ids", []))
            if event.id not in ids:
                ids.append(event.id)
            index["event_ids"] = ids
            digests = dict(index.get("event_digests", {}))
            digests[event.id] = digest
            index["event_digests"] = digests
            return event

        return mutate_index(self.workspace, persist)

    def _put_keyed(
        self,
        payload: dict[str, Any],
        *,
        item_id: str,
        ids_key: str,
        digests_key: str,
        project_id: str,
        restore: Callable[[dict[str, Any]], T],
    ) -> T:
        def persist(index: dict[str, Any]) -> T:
            digest = put_payload(self.workspace, payload)
            ids = list(index.get(ids_key, []))
            if item_id not in ids:
                ids.append(item_id)
            index[ids_key] = ids
            digests = dict(index.get(digests_key, {}))
            digests[item_id] = digest
            index[digests_key] = digests
            by_project = dict(index.get("by_project", {}))
            project_ids = list(by_project.get(project_id, []))
            if item_id not in project_ids:
                project_ids.append(item_id)
            by_project[project_id] = project_ids
            index["by_project"] = by_project
            return restore(payload)

        return mutate_index(self.workspace, persist)

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
        acl_epoch: int,
        operation: str,
        object_id: str,
        reason: str,
    ) -> None:
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=operation,
            object_kind="department_handoff",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
