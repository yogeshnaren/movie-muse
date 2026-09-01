"""Deny-by-default authorization authority with versioned permission snapshots."""

from __future__ import annotations

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.errors import AuthorizationError
from movie_muse.authorization.policy import ROLE_ACTIONS, craft_decision_allowed, role_allows
from movie_muse.authorization.projections import compose_modes, project_view as build_project_view
from movie_muse.authorization.types import (
    Action,
    AuthContext,
    Decision,
    DecisionEffect,
    Mode,
    ProjectView,
    Resource,
    ResourceKind,
    parse_action,
)
from movie_muse.identity.api import (
    IdentityService,
    Membership,
    Principal,
    PrincipalKind,
    Role,
    UnknownPrincipalError,
)
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.schemas.api import Project


class AuthorizationService:
    """Local ACL authority. Cached grants are identified by permission_snapshot_id."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        identity: IdentityService,
        audit: AuditLog | None = None,
    ) -> None:
        self.workspace = workspace
        self.identity = identity
        self.audit = audit

    def permission_snapshot_id(self) -> str:
        return self.identity.permission_snapshot_id()

    def authorize(
        self,
        principal: Principal,
        action: Action | str,
        resource: Resource,
        *,
        acl_epoch: int,
        context: AuthContext | None = None,
    ) -> Decision:
        ctx = context or AuthContext()
        snapshot = self.identity.permission_snapshot_id()
        parsed = parse_action(action)
        decision = self._evaluate(
            principal,
            parsed,
            str(action.value if isinstance(action, Action) else action),
            resource,
            acl_epoch=acl_epoch,
            snapshot_id=snapshot,
            context=ctx,
        )
        if ctx.audit:
            self._audit_decision(decision, principal, resource, ctx)
        return decision

    def require(
        self,
        principal: Principal,
        action: Action | str,
        resource: Resource,
        *,
        acl_epoch: int,
        context: AuthContext | None = None,
    ) -> Decision:
        decision = self.authorize(
            principal, action, resource, acl_epoch=acl_epoch, context=context
        )
        if decision.denied:
            raise AuthorizationError(
                f"denied {decision.action} on {decision.resource_kind}:{decision.resource_id} "
                f"({decision.reason})",
                decision=decision,
            )
        return decision

    def project_view(
        self,
        mode: Mode | tuple[Mode, ...] | list[Mode],
        principal: Principal,
        project: Project,
        *,
        document_id: str | None = None,
    ) -> ProjectView:
        membership = self.identity.accepted_membership_for(
            principal.actor_id,
            project_id=project.id,
            organization_id=project.organization_id,
        )
        granted: set[Action] = set()
        if membership is not None:
            granted.update(ROLE_ACTIONS.get(membership.role, frozenset()))
            if membership.role is Role.DEPARTMENT_CONTRIBUTOR:
                granted.add(Action.CONFIRM_CRAFT_DECISION)
        return build_project_view(
            mode,
            principal,
            project_id=project.id,
            organization_id=project.organization_id,
            workspace=self.workspace,
            granted_actions=frozenset(granted),
            document_id=document_id,
        )

    def resource_for_project(
        self,
        project_id: str,
        *,
        kind: ResourceKind = ResourceKind.PROJECT,
        resource_id: str | None = None,
        department: str | None = None,
        protected: bool = False,
    ) -> Resource:
        binding = self.identity.project_binding(project_id)
        return Resource(
            kind=kind,
            id=resource_id or project_id,
            organization_id=str(binding["organization_id"]),
            project_id=project_id,
            department=department,
            protected=protected,
        )

    def _evaluate(
        self,
        principal: Principal,
        parsed_action: Action | None,
        action_name: str,
        resource: Resource,
        *,
        acl_epoch: int,
        snapshot_id: str,
        context: AuthContext,
    ) -> Decision:
        def deny(reason: str, role: str | None = None) -> Decision:
            return Decision(
                effect=DecisionEffect.DENY,
                action=action_name,
                resource_kind=resource.kind.value,
                resource_id=resource.id,
                principal_id=principal.actor_id,
                reason=reason,
                acl_epoch=acl_epoch,
                snapshot_id=snapshot_id,
                role=role,
            )

        if parsed_action is None:
            return deny("unknown_action")

        current_epoch = self.identity.acl_epoch()
        if acl_epoch != current_epoch:
            return deny("stale_acl_epoch")
        if context.snapshot_id is not None and context.snapshot_id != snapshot_id:
            return deny("stale_snapshot")

        claimed_org = context.claimed_organization_id or principal.organization_id
        if claimed_org != resource.organization_id:
            return deny("tenant_isolation")

        binding: dict[str, str] | None
        try:
            binding = self.identity.project_binding(resource.project_id or resource.id)
        except Exception:
            binding = None
        if resource.kind is ResourceKind.ORGANIZATION:
            if principal.organization_id != resource.organization_id:
                return deny("tenant_isolation")
        elif binding is None:
            return deny("unknown_resource")
        else:
            if str(binding["organization_id"]) != resource.organization_id:
                return deny("confused_deputy")
            if principal.organization_id != str(binding["organization_id"]):
                return deny("tenant_isolation")

        try:
            registered = self.identity.get_actor(principal.actor_id)
        except UnknownPrincipalError:
            return deny("unknown_principal")
        if registered.principal_kind != principal.kind:
            return deny("principal_kind_mismatch")

        project_id = resource.project_id or (str(binding["id"]) if binding is not None else None)
        if project_id is None and resource.kind is not ResourceKind.ORGANIZATION:
            return deny("unknown_resource")

        membership: Membership | None = None
        if project_id is not None:
            membership = self.identity.accepted_membership_for(
                principal.actor_id,
                project_id=project_id,
                organization_id=resource.organization_id,
            )
        if membership is None:
            for item in self.identity.list_memberships():
                if (
                    item.actor_id == principal.actor_id
                    and item.organization_id == resource.organization_id
                ):
                    membership = item
                    break
        if membership is None:
            return deny("no_membership")

        if parsed_action is Action.CONFIRM_CRAFT_DECISION:
            department = resource.department or context.department
            if not craft_decision_allowed(
                principal=principal,
                role=membership.role,
                resource_department=department,
                membership_department=membership.department,
            ):
                return deny("craft_owner_required", role=membership.role.value)
            return self._allow(parsed_action, resource, principal, membership, snapshot_id, acl_epoch)

        if parsed_action in {Action.MERGE, Action.ACCEPT} and resource.protected:
            if not role_allows(membership.role, Action.MANAGE_ACL) and membership.role != Role.OWNER:
                return deny("protected_branch_requires_approval", role=membership.role.value)
            if not context.allow_protected:
                return deny("protected_branch_requires_approval", role=membership.role.value)

        if not role_allows(membership.role, parsed_action):
            return deny("role_denied", role=membership.role.value)

        if principal.kind is PrincipalKind.INTEGRATION_SERVICE and parsed_action in {
            Action.ACCEPT,
            Action.MERGE,
            Action.MANAGE_ACL,
            Action.CONFIRM_CRAFT_DECISION,
            Action.VIEW_SENSITIVE_FINANCIAL,
            Action.VIEW_RIGHTS,
        }:
            return deny("integration_cannot_confirm", role=membership.role.value)

        if context.modes:
            composed = compose_modes(context.modes)
            if not composed.permits(parsed_action):
                return deny("mode_denied", role=membership.role.value)

        return self._allow(parsed_action, resource, principal, membership, snapshot_id, acl_epoch)

    @staticmethod
    def _allow(
        action: Action,
        resource: Resource,
        principal: Principal,
        membership: Membership,
        snapshot_id: str,
        acl_epoch: int,
    ) -> Decision:
        return Decision(
            effect=DecisionEffect.ALLOW,
            action=action.value,
            resource_kind=resource.kind.value,
            resource_id=resource.id,
            principal_id=principal.actor_id,
            reason="allow",
            acl_epoch=acl_epoch,
            snapshot_id=snapshot_id,
            role=membership.role.value,
        )

    def _audit_decision(
        self,
        decision: Decision,
        principal: Principal,
        resource: Resource,
        context: AuthContext,
    ) -> None:
        if self.audit is None:
            return
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=decision.action,
            object_kind=resource.kind.value,
            object_id=resource.id,
            policy_decision=PolicyDecision.ALLOW if decision.allowed else PolicyDecision.DENY,
            acl_epoch=decision.acl_epoch,
            reason=decision.reason,
            correlation_id=context.correlation_id,
            before_revision_id=context.before_revision_id,
            after_revision_id=context.after_revision_id,
        )


def authorize(
    principal: Principal,
    action: Action | str,
    resource: Resource,
    *,
    acl_epoch: int,
    context: AuthContext | None = None,
    authority: AuthorizationService | None = None,
) -> Decision:
    """Deny-by-default entry point. An unbound call (no authority) is a deny."""

    if authority is None:
        return Decision(
            effect=DecisionEffect.DENY,
            action=action.value if isinstance(action, Action) else str(action),
            resource_kind=resource.kind.value,
            resource_id=resource.id,
            principal_id=principal.actor_id,
            reason="no_authority",
            acl_epoch=acl_epoch,
            snapshot_id="",
            role=None,
        )
    return authority.authorize(
        principal, action, resource, acl_epoch=acl_epoch, context=context
    )
