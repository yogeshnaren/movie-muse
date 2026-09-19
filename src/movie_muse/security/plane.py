"""Control plane that boots identity, ACL, and the five MM-046 services."""

from __future__ import annotations

from pathlib import Path

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.evaluation.api import EvaluationService
from movie_muse.identity.api import Actor, IdentityService, Organization, Principal, PrincipalKind
from movie_muse.observability.api import ObservabilityService
from movie_muse.operations.api import OperationsService
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.privacy.api import PrivacyService
from movie_muse.schemas.api import Project, ScreenplayDocument
from movie_muse.security.service import SecurityService


class ControlPlane:
    """Single boot path for security, privacy, observability, evaluation, and operations."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        *,
        organization_id: str,
        project_id: str,
        customer_key: bytes | None = None,
    ) -> None:
        self.workspace = workspace
        self.organization_id = organization_id
        self.project_id = project_id
        self.identity = IdentityService(workspace)
        self.audit = AuditLog(workspace)
        self.authorization = AuthorizationService(workspace, self.identity, audit=self.audit)
        self.security = SecurityService(
            workspace,
            self.authorization,
            self.audit,
            organization_id=organization_id,
            project_id=project_id,
            customer_key=customer_key,
        )
        self.privacy = PrivacyService(
            workspace,
            self.authorization,
            self.audit,
            organization_id=organization_id,
            project_id=project_id,
        )
        self.observability = ObservabilityService(
            workspace,
            self.authorization,
            self.audit,
            organization_id=organization_id,
            project_id=project_id,
        )
        self.evaluation = EvaluationService(
            workspace,
            self.authorization,
            self.identity,
            self.audit,
            organization_id=organization_id,
            project_id=project_id,
        )
        self.operations = OperationsService(
            workspace,
            self.authorization,
            self.audit,
            organization_id=organization_id,
            project_id=project_id,
            ready_check=self.security.assert_ready,
        )

    @classmethod
    def open(
        cls,
        root: Path,
        project: Project,
        document: ScreenplayDocument,
        *,
        branch_id: str,
        customer_key: bytes | None = None,
        organization_name: str = "Studio",
    ) -> ControlPlane:
        workspace = LocalWorkspace(root)
        workspace.open_project(project, document, branch_id=branch_id)
        plane = cls(
            workspace,
            organization_id=project.organization_id,
            project_id=project.id,
            customer_key=customer_key,
        )
        owner = Actor(
            id=project.owner_actor_id,
            display_name="Owner",
            principal_kind=PrincipalKind.HUMAN,
            organization_id=project.organization_id,
            created_at=project.created_at,
        )
        plane.identity.bootstrap(
            organization=Organization(
                id=project.organization_id,
                name=organization_name,
                created_at=project.created_at,
            ),
            project=project,
            owner=owner,
        )
        return plane

    @property
    def principal(self) -> Principal:
        binding = self.identity.project_binding(self.project_id)
        return self.identity.principal(binding["owner_actor_id"])

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()

    def close(self) -> None:
        self.workspace.close()
