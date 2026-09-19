"""Revision-aware regeneration and public-module import boundaries."""

from __future__ import annotations

import ast
import threading
from dataclasses import replace
from pathlib import Path

from movie_muse.artifacts.api import ArtifactClassification, ArtifactService, ArtifactType
from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.identity.api import Actor, IdentityService, Organization, PrincipalKind
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import ArtifactStatus


def test_regeneration_after_source_revision_change_has_new_checksum_and_is_draft(
    artifact_stack,
) -> None:
    template = artifact_stack.artifacts.register_template(
        project_id=artifact_stack.project.id,
        version="1",
        renderer_version="json/1",
        body="Source-sensitive render",
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    artifact = artifact_stack.artifacts.create_artifact(
        project_id=artifact_stack.project.id,
        artifact_type=ArtifactType.DOCUMENT,
        title="Revision-linked artifact",
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    original = artifact_stack.artifacts.create_version(
        artifact.id,
        inputs={"constant": True},
        source_revision_id=artifact_stack.revisions.canon_head_id(),
        template_id=template.id,
        template_version=template.version,
        renderer_version=template.renderer_version,
        classification=ArtifactClassification.INTERNAL,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    current = artifact_stack.revisions.load_revision(
        artifact_stack.revisions.canon_head_id()
    )
    changed_blocks = tuple(
        replace(block, text=f"{block.text} Revised.")
        if block.kind.value == "action"
        else block
        for block in current.blocks
    )
    saved = artifact_stack.revisions.save_document(
        replace(current, blocks=changed_blocks),
        actor_id=artifact_stack.owner.id,
    )

    regenerated = artifact_stack.artifacts.regenerate(
        original.version.id,
        source_revision_id=saved.revision_id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )

    assert regenerated.version.id != original.version.id
    assert regenerated.version.source_revision_id == saved.revision_id
    assert regenerated.version.checksum != original.version.checksum
    assert regenerated.status is ArtifactStatus.DRAFT
    comparison = artifact_stack.artifacts.compare(
        original.version.id,
        regenerated.version.id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    assert comparison.source_revision_changed
    assert comparison.checksum_changed
    assert not comparison.inputs_changed


def test_artifacts_import_other_modules_only_through_public_api() -> None:
    package = Path(__file__).parents[2] / "src" / "movie_muse" / "artifacts"
    violations: list[tuple[str, str]] = []
    for source_path in package.glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            if not node.module.startswith("movie_muse."):
                continue
            parts = node.module.split(".")
            if len(parts) < 2 or parts[1] == "artifacts":
                continue
            if not node.module.endswith(".api"):
                violations.append((source_path.name, node.module))
    assert violations == []


def test_artifacts_use_workspace_meta_and_blobs_without_new_tables(artifact_stack) -> None:
    before = {
        str(row["name"])
        for row in artifact_stack.workspace.store.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    artifact_stack.artifacts.create_artifact(
        project_id=artifact_stack.project.id,
        artifact_type=ArtifactType.PACKAGE,
        title="Storage probe",
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    after = {
        str(row["name"])
        for row in artifact_stack.workspace.store.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert after == before
    digest = artifact_stack.workspace.store.get_meta("artifacts.index_digest")
    assert digest is not None
    assert artifact_stack.workspace.store.blobs.exists(digest)


def test_concurrent_creates_keep_both_artifacts(tmp_path, project_bundle) -> None:
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
            revisions = RevisionService(workspace)
            artifacts = ArtifactService(workspace, authorization, revisions, AuditLog(workspace))
            principal = identity_conn.principal(owner.id)
            barrier.wait(timeout=5)
            artifact = artifacts.create_artifact(
                project_id=project.id,
                artifact_type=ArtifactType.DOCUMENT,
                title=f"Concurrent {index}",
                principal=principal,
                acl_epoch=identity_conn.acl_epoch(),
            )
            created[index] = artifact.id
        except Exception as exc:
            errors[index] = exc
        finally:
            if workspace is not None:
                workspace.close()

    threads = [threading.Thread(target=worker, args=(0,)), threading.Thread(target=worker, args=(1,))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert errors == [None, None]
    assert created[0] and created[1] and created[0] != created[1]
    workspace = LocalWorkspace(root)
    identity_conn = IdentityService(workspace)
    artifacts = ArtifactService(
        workspace,
        AuthorizationService(workspace, identity_conn),
        RevisionService(workspace),
    )
    listed = artifacts.list_artifacts(
        project.id,
        principal=identity_conn.principal(owner.id),
        acl_epoch=identity_conn.acl_epoch(),
    )
    assert {item.id for item in listed} == set(created)
