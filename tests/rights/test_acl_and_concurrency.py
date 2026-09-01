"""ACL gates, integration candidates, and concurrent registry writes."""

from __future__ import annotations

import threading

import pytest

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import Action, AuthorizationError, AuthorizationService
from movie_muse.identity.api import Actor, IdentityService, Organization, PrincipalKind, Role
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.rights.api import (
    HumanValidationError,
    PermittedUse,
    PermittedUseDeniedError,
    RightsService,
    SourceClassification,
    SourceValidationState,
)

LICENSED_USES = (
    PermittedUse.RETRIEVAL,
    PermittedUse.CITATION,
    PermittedUse.GENERATION,
    PermittedUse.FORECAST,
    PermittedUse.EXPORT_DISCLOSURE,
)


def test_producer_denied_view_rights_cannot_register_or_export(
    rights_stack, member, licensed_source
) -> None:
    producer = member(Role.PRODUCER)
    with pytest.raises(AuthorizationError):
        rights_stack.rights.register_source(
            project_id=rights_stack.project.id,
            title="Producer corpus",
            classification=SourceClassification.LICENSED,
            principal=producer,
            acl_epoch=rights_stack.epoch,
            permitted_uses=LICENSED_USES,
        )
    source = licensed_source
    with pytest.raises(AuthorizationError):
        rights_stack.rights.export_source_disclosure(
            source.source_id, principal=producer, acl_epoch=rights_stack.epoch
        )
    with pytest.raises(AuthorizationError):
        rights_stack.rights.list_sources(
            rights_stack.project.id, principal=producer, acl_epoch=rights_stack.epoch
        )
    decision = rights_stack.authorization.authorize(
        producer,
        Action.VIEW_RIGHTS,
        rights_stack.authorization.resource_for_project(rights_stack.project.id),
        acl_epoch=rights_stack.epoch,
    )
    assert decision.denied


def test_writer_director_viewer_cannot_manage_registry(rights_stack, member) -> None:
    for role in (Role.WRITER, Role.DIRECTOR, Role.VIEWER):
        principal = member(role)
        with pytest.raises(AuthorizationError):
            rights_stack.rights.register_source(
                project_id=rights_stack.project.id,
                title=f"{role.value} corpus",
                classification=SourceClassification.USER_OWNED,
                principal=principal,
                acl_epoch=rights_stack.epoch,
                permitted_uses=LICENSED_USES,
            )


def test_administrator_can_register_like_owner(rights_stack, member) -> None:
    admin = member(Role.ADMINISTRATOR)
    source = rights_stack.rights.register_source(
        project_id=rights_stack.project.id,
        title="Admin licensed stills",
        classification=SourceClassification.LICENSED,
        principal=admin,
        acl_epoch=rights_stack.epoch,
        permitted_uses=LICENSED_USES,
        license_summary="admin registered",
    )
    assert source.validation_state is SourceValidationState.VALIDATED
    assert source.validated_by == admin.actor_id


def test_integration_candidate_cannot_be_used_until_human_validation(
    rights_stack, member
) -> None:
    bot = member(Role.INTEGRATION_SERVICE, integration=True)
    candidate = rights_stack.rights.register_source(
        project_id=rights_stack.project.id,
        title="Ingested research pack",
        classification=SourceClassification.LICENSED,
        principal=bot,
        acl_epoch=rights_stack.epoch,
        permitted_uses=LICENSED_USES,
        license_summary="vendor feed",
    )
    assert candidate.origin.value == "integration"
    assert candidate.validation_state is SourceValidationState.UNVALIDATED
    with pytest.raises(PermittedUseDeniedError, match="unvalidated_candidate"):
        rights_stack.rights.require_permitted_use(candidate.source_id, PermittedUse.CITATION)
    with pytest.raises(HumanValidationError):
        rights_stack.rights.validate_source(
            candidate.source_id, principal=bot, acl_epoch=rights_stack.epoch
        )
    validated = rights_stack.rights.validate_source(
        candidate.source_id,
        principal=rights_stack.principal,
        acl_epoch=rights_stack.epoch,
    )
    assert validated.version == 2
    assert validated.is_human_validated
    assert rights_stack.rights.require_permitted_use(
        candidate.source_id, PermittedUse.CITATION
    ).allowed


def test_concurrent_register_source_keeps_both_records(tmp_path, project_bundle) -> None:
    project, document, branch_id = project_bundle
    root = tmp_path / "ws"
    bootstrap = LocalWorkspace(root)
    bootstrap.open_project(project, document, branch_id=branch_id)
    identity = IdentityService(bootstrap)
    owner = Actor(
        id=project.owner_actor_id,
        display_name="Owner",
        principal_kind=PrincipalKind.HUMAN,
        organization_id=project.organization_id,
        created_at="2026-09-01T00:00:00Z",
    )
    identity.bootstrap(
        organization=Organization(
            id=project.organization_id,
            name="Studio",
            created_at="2026-09-01T00:00:00Z",
        ),
        project=project,
        owner=owner,
    )
    bootstrap.close()
    barrier = threading.Barrier(2)
    created: list[str | None] = [None, None]
    errors: list[BaseException | None] = [None, None]

    def worker(index: int) -> None:
        workspace = None
        try:
            workspace = LocalWorkspace(root)
            identity_conn = IdentityService(workspace)
            authorization = AuthorizationService(workspace, identity_conn)
            rights = RightsService(workspace, authorization, AuditLog(workspace))
            principal = identity_conn.principal(owner.id)
            barrier.wait(timeout=5)
            source = rights.register_source(
                project_id=project.id,
                title=f"Concurrent corpus {index}",
                classification=SourceClassification.LICENSED,
                principal=principal,
                acl_epoch=identity_conn.acl_epoch(),
                permitted_uses=LICENSED_USES,
                license_summary=f"license-{index}",
            )
            created[index] = source.source_id
        except Exception as exc:
            errors[index] = exc
        finally:
            if workspace is not None:
                workspace.close()

    threads = [
        threading.Thread(target=worker, args=(0,)),
        threading.Thread(target=worker, args=(1,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert errors == [None, None]
    assert created[0] and created[1] and created[0] != created[1]
    workspace = LocalWorkspace(root)
    identity_conn = IdentityService(workspace)
    rights = RightsService(workspace, AuthorizationService(workspace, identity_conn))
    listed = rights.list_sources(
        project.id,
        principal=identity_conn.principal(owner.id),
        acl_epoch=identity_conn.acl_epoch(),
    )
    assert {item.source_id for item in listed} == set(created)
    workspace.close()
