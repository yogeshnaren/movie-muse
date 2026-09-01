"""One immutable lifecycle for document, table, media, and package artifacts."""

from __future__ import annotations

from dataclasses import replace

import pytest

from movie_muse.artifacts.api import (
    ArtifactClassification,
    ArtifactImmutableError,
    ArtifactType,
)
from movie_muse.schemas.api import ArtifactStatus


def _template(stack):
    return stack.artifacts.register_template(
        project_id=stack.project.id,
        template_id="tmpl_generic",
        version="1.0",
        renderer_version="deterministic-json/1",
        body="{{ source_revision }} :: {{ inputs }}",
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )


def _version(stack, artifact_id: str, *, inputs=None):
    return stack.artifacts.create_version(
        artifact_id,
        inputs=(
            {"sections": ["overview"], "page_count": 1}
            if inputs is None
            else inputs
        ),
        source_revision_id=stack.revisions.canon_head_id(),
        template_id="tmpl_generic",
        template_version="1.0",
        renderer_version="deterministic-json/1",
        classification=ArtifactClassification.INTERNAL,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        evidence_bundle_ids=("evd_external_contract",),
        rights_record_ids=("rgt_external_contract",),
    )


def test_four_generic_types_share_one_store_and_lifecycle(artifact_stack) -> None:
    _template(artifact_stack)
    created = [
        artifact_stack.artifacts.create_artifact(
            project_id=artifact_stack.project.id,
            artifact_type=artifact_type,
            title=f"{artifact_type.value.title()} output",
            principal=artifact_stack.principal,
            acl_epoch=artifact_stack.epoch,
        )
        for artifact_type in ArtifactType
    ]
    versions = [_version(artifact_stack, artifact.id) for artifact in created]

    assert {artifact.artifact_type for artifact in created} == {
        "document",
        "table",
        "media",
        "package",
    }
    assert all(view.status is ArtifactStatus.DRAFT for view in versions)
    assert all(view.version.evidence_bundle_ids for view in versions)
    assert all(view.version.rights_record_ids for view in versions)
    assert artifact_stack.workspace.store.get_meta("artifacts.index_digest")
    assert len(artifact_stack.artifacts.list_artifacts(
        artifact_stack.project.id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )) == 4


def test_version_inputs_and_content_are_immutable(artifact_stack) -> None:
    _template(artifact_stack)
    artifact = artifact_stack.artifacts.create_artifact(
        project_id=artifact_stack.project.id,
        artifact_type=ArtifactType.DOCUMENT,
        title="Locked version",
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    mutable_inputs = {"nested": {"value": "original"}, "rows": [1, 2]}
    view = _version(artifact_stack, artifact.id, inputs=mutable_inputs)
    mutable_inputs["nested"]["value"] = "changed"
    stored = artifact_stack.artifacts.get_version(
        view.version.id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )

    assert stored.record.inputs["nested"]["value"] == "original"
    with pytest.raises(TypeError):
        stored.record.inputs["new"] = "forbidden"
    with pytest.raises(ArtifactImmutableError):
        artifact_stack.artifacts.update_version(view.version.id, checksum="forged")
    with pytest.raises(ArtifactImmutableError):
        artifact_stack.artifacts.delete_version(view.version.id)
    with pytest.raises(AttributeError):
        replace(view.version, checksum="forged").checksum = "other"

    replacement = _version(
        artifact_stack,
        artifact.id,
        inputs={"nested": {"value": "changed"}, "rows": [1, 2]},
    )
    assert replacement.version.id != view.version.id
    assert replacement.version.checksum != view.version.checksum


@pytest.mark.parametrize(
    "inputs",
    [
        {},
        {"title": "Café", "count": 0},
        {"rows": [{"scene": 2, "cast": ["Ada", "Bo"]}], "enabled": True},
        {"metadata": {"b": None, "a": [3, 2, 1]}},
    ],
)
def test_deterministic_render_property(artifact_stack, inputs) -> None:
    _template(artifact_stack)
    artifact = artifact_stack.artifacts.create_artifact(
        project_id=artifact_stack.project.id,
        artifact_type=ArtifactType.PACKAGE,
        title="Deterministic package",
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    version = _version(artifact_stack, artifact.id, inputs=inputs)

    first = artifact_stack.artifacts.render_version(
        version.version.id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    second = artifact_stack.artifacts.render_version(
        version.version.id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    regenerated = artifact_stack.artifacts.regenerate(
        version.version.id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )

    assert first.content == second.content
    assert first.render.checksum == second.render.checksum == version.version.checksum
    assert regenerated.version.id != version.version.id
    assert regenerated.version.checksum == version.version.checksum
    assert regenerated.status is ArtifactStatus.DRAFT


def test_compare_versions_reports_content_source_status_and_input_changes(
    artifact_stack,
) -> None:
    _template(artifact_stack)
    artifact = artifact_stack.artifacts.create_artifact(
        project_id=artifact_stack.project.id,
        artifact_type=ArtifactType.TABLE,
        title="Comparison",
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    left = _version(artifact_stack, artifact.id, inputs={"rows": 1, "label": "A"})
    artifact_stack.artifacts.transition_review(
        left.version.id,
        ArtifactStatus.IN_REVIEW,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )
    right = _version(artifact_stack, artifact.id, inputs={"rows": 2, "label": "A"})

    comparison = artifact_stack.artifacts.compare(
        left.version.id,
        right.version.id,
        principal=artifact_stack.principal,
        acl_epoch=artifact_stack.epoch,
    )

    assert comparison.checksum_changed
    assert comparison.status_changed
    assert not comparison.source_revision_changed
    assert comparison.inputs_changed
    assert comparison.changed_input_keys == ("rows",)
