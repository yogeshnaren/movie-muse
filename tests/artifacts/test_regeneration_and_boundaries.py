"""Revision-aware regeneration and public-module import boundaries."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

from movie_muse.artifacts.api import ArtifactClassification, ArtifactType
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
