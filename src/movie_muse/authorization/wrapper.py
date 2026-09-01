"""ACL facade in front of RevisionService mutating commands. Does not edit revisions."""

from __future__ import annotations

from pathlib import Path

from movie_muse.authorization.errors import AuthorizationError
from movie_muse.authorization.service import AuthorizationService
from movie_muse.authorization.types import Action, AuthContext, Resource, ResourceKind
from movie_muse.identity.api import IdentityService, Principal, UnknownPrincipalError
from movie_muse.persistence.api import SaveAck
from movie_muse.revisions.api import DEFAULT_DEVICE_ID, Branch, Merge, Proposal, RevisionService
from movie_muse.schemas.api import ChangeSet, ScreenplayDocument


class AuthorizedRevisionService:
    """Re-check ACL at the command boundary, then again conceptually for workers.

    Mutating RevisionService methods are gated here. The revisions module is
    unchanged; hosts should use this wrapper rather than RevisionService for
    commands that require craft/ACL checks.
    """

    def __init__(
        self,
        revisions: RevisionService,
        authorization: AuthorizationService,
        identity: IdentityService,
    ) -> None:
        self.revisions = revisions
        self.authorization = authorization
        self.identity = identity
        self.workspace = revisions.workspace

    def apply_change_set(
        self,
        change_set: ChangeSet,
        *,
        actor_id: str,
        branch_ref: str | None = None,
        device_id: str | None = None,
        allow_protected: bool = False,
    ) -> SaveAck:
        principal = self._principal(actor_id)
        resource = self._branch_resource(branch_ref)
        before = resource_head(self.revisions, branch_ref)
        ctx = AuthContext(
            allow_protected=allow_protected,
            before_revision_id=before,
            snapshot_id=self.authorization.permission_snapshot_id(),
        )
        self._require(principal, Action.ACCEPT, resource, context=ctx)
        return self.revisions.apply_change_set(
            change_set,
            actor_id=actor_id,
            branch_ref=branch_ref,
            device_id=device_id or DEFAULT_DEVICE_ID,
            allow_protected=self._pass_protected(principal, resource, allow_protected),
        )

    def save_document(
        self,
        document: ScreenplayDocument,
        *,
        actor_id: str,
        branch_ref: str | None = None,
        device_id: str | None = None,
        allow_protected: bool = False,
    ) -> SaveAck:
        principal = self._principal(actor_id)
        resource = self._branch_resource(branch_ref)
        self._require(
            principal,
            Action.ACCEPT,
            resource,
            context=AuthContext(
                allow_protected=allow_protected,
                snapshot_id=self.authorization.permission_snapshot_id(),
            ),
        )
        return self.revisions.save_document(
            document,
            actor_id=actor_id,
            branch_ref=branch_ref,
            device_id=device_id or DEFAULT_DEVICE_ID,
            allow_protected=self._pass_protected(principal, resource, allow_protected),
        )

    def merge_into(
        self,
        *,
        source_branch: str,
        target_branch: str,
        actor_id: str,
        device_id: str | None = None,
        allow_protected: bool = False,
    ) -> Merge:
        principal = self._principal(actor_id)
        resource = self._branch_resource(target_branch)
        before = resource_head(self.revisions, target_branch)
        self._require(
            principal,
            Action.MERGE,
            resource,
            context=AuthContext(
                allow_protected=allow_protected,
                before_revision_id=before,
                snapshot_id=self.authorization.permission_snapshot_id(),
            ),
        )
        return self.revisions.merge_into(
            source_branch=source_branch,
            target_branch=target_branch,
            actor_id=actor_id,
            device_id=device_id or DEFAULT_DEVICE_ID,
            allow_protected=self._pass_protected(principal, resource, allow_protected),
        )

    def accept_proposal(
        self,
        proposal_id: str,
        *,
        actor_id: str,
        branch_ref: str | None = None,
        device_id: str | None = None,
        allow_protected: bool = False,
    ) -> tuple[Proposal, SaveAck]:
        principal = self._principal(actor_id)
        resource = self._branch_resource(branch_ref)
        self._require(
            principal,
            Action.ACCEPT,
            resource,
            context=AuthContext(
                allow_protected=allow_protected,
                snapshot_id=self.authorization.permission_snapshot_id(),
            ),
        )
        return self.revisions.accept_proposal(
            proposal_id,
            actor_id=actor_id,
            branch_ref=branch_ref,
            device_id=device_id or DEFAULT_DEVICE_ID,
            allow_protected=self._pass_protected(principal, resource, allow_protected),
        )

    def store_proposal(self, proposal: Proposal, *, actor_id: str) -> Proposal:
        principal = self._principal(actor_id)
        resource = self._project_resource()
        self._require(principal, Action.PROPOSE, resource)
        return self.revisions.store_proposal(proposal)

    def retarget_branch(
        self,
        branch_ref: str,
        revision_id: str,
        *,
        actor_id: str,
        allow_protected: bool = False,
    ) -> Branch:
        principal = self._principal(actor_id)
        resource = self._branch_resource(branch_ref)
        self._require(
            principal,
            Action.MERGE,
            resource,
            context=AuthContext(
                allow_protected=allow_protected,
                snapshot_id=self.authorization.permission_snapshot_id(),
            ),
        )
        return self.revisions.retarget_branch(
            branch_ref,
            revision_id,
            actor_id=actor_id,
            allow_protected=self._pass_protected(principal, resource, allow_protected),
        )

    def export_document(self, destination: Path, *, actor_id: str, document_id: str | None = None) -> Path:
        principal = self._principal(actor_id)
        resource = self._project_resource()
        self._require(principal, Action.EXPORT, resource)
        return self.revisions.export_document(destination, document_id=document_id)

    def confirm_craft_decision(
        self,
        *,
        actor_id: str,
        department: str,
        operation_id: str,
    ) -> None:
        """Authority-side craft confirmation. Workers call the same authorize()."""

        principal = self._principal(actor_id)
        resource = self.authorization.resource_for_project(
            self._project_id(),
            kind=ResourceKind.OPERATION,
            resource_id=operation_id,
            department=department,
        )
        self._require(
            principal,
            Action.CONFIRM_CRAFT_DECISION,
            resource,
            context=AuthContext(department=department),
        )

    def _principal(self, actor_id: str) -> Principal:
        try:
            return self.identity.principal(actor_id)
        except UnknownPrincipalError as exc:
            raise AuthorizationError(f"unknown principal: {actor_id}") from exc

    def _require(
        self,
        principal: Principal,
        action: Action,
        resource: Resource,
        context: AuthContext | None = None,
    ) -> None:
        ctx = context or AuthContext(snapshot_id=self.authorization.permission_snapshot_id())
        if ctx.snapshot_id is None:
            ctx = AuthContext(
                snapshot_id=self.authorization.permission_snapshot_id(),
                department=ctx.department,
                allow_protected=ctx.allow_protected,
                correlation_id=ctx.correlation_id,
                before_revision_id=ctx.before_revision_id,
                after_revision_id=ctx.after_revision_id,
                audit=ctx.audit,
                modes=ctx.modes,
                claimed_organization_id=ctx.claimed_organization_id,
            )
        self.authorization.require(
            principal,
            action,
            resource,
            acl_epoch=self.identity.acl_epoch(),
            context=ctx,
        )

    def _project_id(self) -> str:
        project_id = self.workspace.store.get_meta("active_project_id")
        if project_id is None:
            raise AuthorizationError("workspace has no active project")
        return project_id

    def _project_resource(self) -> Resource:
        return self.authorization.resource_for_project(self._project_id())

    def _branch_resource(self, branch_ref: str | None) -> Resource:
        project_id = self._project_id()
        protected = False
        resource_id = branch_ref or project_id
        if branch_ref is not None:
            try:
                branch = self.revisions.get_branch(branch_ref)
                protected = branch.protected
                resource_id = branch.id
            except Exception:
                protected = False
        else:
            try:
                branch = self.revisions.canon_branch()
                protected = branch.protected
                resource_id = branch.id
            except Exception:
                protected = False
        return self.authorization.resource_for_project(
            project_id,
            kind=ResourceKind.BRANCH,
            resource_id=resource_id,
            protected=protected,
        )

    def _pass_protected(self, principal: Principal, resource: Resource, requested: bool) -> bool:
        if not resource.protected:
            return requested
        # Only owner/manage-ACL principals may set allow_protected for the inner service.
        try:
            self.authorization.require(
                principal,
                Action.MANAGE_ACL,
                resource,
                acl_epoch=self.identity.acl_epoch(),
                context=AuthContext(
                    allow_protected=True,
                    snapshot_id=self.authorization.permission_snapshot_id(),
                    audit=False,
                ),
            )
        except AuthorizationError:
            return False
        return requested


def resource_head(revisions: RevisionService, branch_ref: str | None) -> str | None:
    try:
        if branch_ref is None:
            return revisions.canon_head_id()
        return revisions.get_branch(branch_ref).head_revision_id
    except Exception:
        return None
