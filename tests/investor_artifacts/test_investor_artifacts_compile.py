"""Investor packs cite current reviewed artifacts, budget, and scenarios."""

from __future__ import annotations

import pytest

from movie_muse.artifacts.api import ArtifactType
from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Role
from movie_muse.investor_artifacts.api import (
    DISCLAIMER,
    PackKind,
    PackNotFoundError,
    StaleEvidenceError,
    UnsupportedClaimError,
)
from movie_muse.rights.api import PermittedUse, PermittedUseDeniedError, UnlicensedSourceError


def test_compile_deck_traces_claims_to_current_evidence(
    compiled_pack, compiled_budget, forecast_record, approved_source, investor_stack
) -> None:
    pack = compiled_pack
    assert pack.id.startswith("ivp_")
    assert pack.kind is PackKind.DECK
    assert pack.disclaimer == DISCLAIMER
    assert pack.previewed is False
    assert pack.approved is False
    assert pack.labeled_stale is False
    assert pack.budget_id == compiled_budget.id
    assert pack.forecast_id == forecast_record.id
    assert pack.source_version_ids == (approved_source,)
    labels = {item.label: item for item in pack.claims}
    assert labels["budget_total"].value == format(compiled_budget.total, "f")
    assert labels["budget_total"].evidence_ref == compiled_budget.id
    assert labels["p50"].value == str(forecast_record.outcome("P50").value)
    assert labels["reviewed_source"].value == approved_source
    for claim in pack.claims:
        assert claim.id.startswith("ivc_")
        assert claim.evidence_ref
        assert claim.method
        assert claim.data_as_of == "2024-12-31"
    assert pack.citations[0].use == PermittedUse.CITATION.value
    artifact = investor_stack.artifacts.get_artifact(
        pack.artifact_id, principal=investor_stack.principal, acl_epoch=investor_stack.epoch
    )
    assert artifact.artifact_type == ArtifactType.DOCUMENT.value
    listed = investor_stack.investor.list_packs(
        investor_stack.project.id,
        principal=investor_stack.principal,
        acl_epoch=investor_stack.epoch,
    )
    assert pack.id in {item.id for item in listed}
    operations = {record.operation for record in investor_stack.audit.list_records()}
    assert "investor.compile" in operations


def test_one_pager_and_data_room_kinds(build_pack, investor_stack) -> None:
    one_pager = build_pack(kind=PackKind.ONE_PAGER)
    data_room = build_pack(kind=PackKind.DATA_ROOM)
    assert one_pager.kind is PackKind.ONE_PAGER
    assert data_room.kind is PackKind.DATA_ROOM
    one_artifact = investor_stack.artifacts.get_artifact(
        one_pager.artifact_id,
        principal=investor_stack.principal,
        acl_epoch=investor_stack.epoch,
    )
    room_artifact = investor_stack.artifacts.get_artifact(
        data_room.artifact_id,
        principal=investor_stack.principal,
        acl_epoch=investor_stack.epoch,
    )
    assert one_artifact.artifact_type == ArtifactType.DOCUMENT.value
    assert room_artifact.artifact_type == ArtifactType.PACKAGE.value


def test_unreviewed_source_cannot_be_cited(build_pack, draft_source) -> None:
    with pytest.raises(UnsupportedClaimError, match="reviewed and approved"):
        build_pack(source_version_ids=(draft_source,))


def test_empty_sources_fail_closed(build_pack) -> None:
    with pytest.raises(UnsupportedClaimError, match="at least one reviewed source"):
        build_pack(source_version_ids=())


def test_missing_citation_rights_fail_closed(build_pack, retrieval_only_source) -> None:
    with pytest.raises((PermittedUseDeniedError, UnlicensedSourceError, UnsupportedClaimError)):
        build_pack(rights_source_id=retrieval_only_source.source_id)


def test_empty_rights_source_fail_closed(build_pack) -> None:
    with pytest.raises(UnsupportedClaimError, match="rights source"):
        build_pack(rights_source_id="")


def test_stale_budget_cannot_compile_current_pack(
    investor_stack, compiled_budget, build_pack
) -> None:
    investor_stack.budget.notify_schedule_changed(
        compiled_budget.schedule_id,
        principal=investor_stack.principal,
        acl_epoch=investor_stack.epoch,
    )
    with pytest.raises(StaleEvidenceError):
        build_pack()


def test_viewer_cannot_read_pack(compiled_pack, investor_stack, member) -> None:
    viewer = member(Role.VIEWER)
    with pytest.raises(AuthorizationError):
        investor_stack.investor.get_pack(
            compiled_pack.id,
            principal=viewer,
            acl_epoch=investor_stack.identity.acl_epoch(),
        )


def test_writer_cannot_read_financial_pack(compiled_pack, investor_stack, member) -> None:
    writer = member(Role.WRITER)
    with pytest.raises(AuthorizationError):
        investor_stack.investor.get_pack(
            compiled_pack.id,
            principal=writer,
            acl_epoch=investor_stack.identity.acl_epoch(),
        )


def test_unknown_pack_is_not_found(investor_stack) -> None:
    with pytest.raises(PackNotFoundError):
        investor_stack.investor.get_pack(
            "ivp_missing",
            principal=investor_stack.principal,
            acl_epoch=investor_stack.epoch,
        )
