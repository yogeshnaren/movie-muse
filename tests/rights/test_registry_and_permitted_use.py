"""Source registration, immutable versions, and permitted-use fail-closed gates."""

from __future__ import annotations

import pytest

from movie_muse.rights.api import (
    PermittedUse,
    PermittedUseDeniedError,
    SourceClassification,
    SourceNotFoundError,
    SourceValidationState,
    UnlicensedSourceError,
)

LICENSED_USES = (
    PermittedUse.RETRIEVAL,
    PermittedUse.CITATION,
    PermittedUse.GENERATION,
    PermittedUse.FORECAST,
    PermittedUse.EXPORT_DISCLOSURE,
)


def test_unlicensed_source_use_is_blocked(rights_stack) -> None:
    source = rights_stack.rights.register_source(
        project_id=rights_stack.project.id,
        title="Scraped torrent dump",
        classification=SourceClassification.UNLICENSED,
        principal=rights_stack.principal,
        acl_epoch=rights_stack.epoch,
        permitted_uses=(),
    )
    with pytest.raises(UnlicensedSourceError):
        rights_stack.rights.require_permitted_use(source.source_id, PermittedUse.CITATION)
    with pytest.raises(UnlicensedSourceError):
        rights_stack.rights.export_source_disclosure(
            source.source_id,
            principal=rights_stack.principal,
            acl_epoch=rights_stack.epoch,
        )
    disallowed = rights_stack.rights.register_source(
        project_id=rights_stack.project.id,
        title="Competitor proprietary bible",
        classification=SourceClassification.DISALLOWED,
        principal=rights_stack.principal,
        acl_epoch=rights_stack.epoch,
    )
    with pytest.raises(UnlicensedSourceError):
        rights_stack.rights.require_permitted_use(disallowed.source_id, PermittedUse.RETRIEVAL)


def test_licensed_source_permits_declared_uses_and_blocks_others(rights_stack, licensed_source) -> None:
    source = licensed_source
    decision = rights_stack.rights.require_permitted_use(
        source.source_id, PermittedUse.CITATION
    )
    assert decision.allowed
    assert decision.rights_record_id == source.rights_record_id
    with pytest.raises(PermittedUseDeniedError):
        rights_stack.rights.require_permitted_use(source.source_id, PermittedUse.TRAINING)

    trained = rights_stack.rights.update_source(
        source.source_id,
        principal=rights_stack.principal,
        acl_epoch=rights_stack.epoch,
        allow_training=True,
        permitted_uses=(*LICENSED_USES, PermittedUse.TRAINING),
    )
    assert trained.version == 2
    assert trained.id != source.id
    assert rights_stack.rights.require_permitted_use(
        source.source_id, PermittedUse.TRAINING
    ).allowed
    history = rights_stack.rights.list_source_versions(
        source.source_id, principal=rights_stack.principal, acl_epoch=rights_stack.epoch
    )
    assert [item.version for item in history] == [1, 2]
    assert history[0].allow_training is False


def test_expired_license_is_denied(rights_stack) -> None:
    source = rights_stack.rights.register_source(
        project_id=rights_stack.project.id,
        title="Expired clip library",
        classification=SourceClassification.LICENSED,
        principal=rights_stack.principal,
        acl_epoch=rights_stack.epoch,
        permitted_uses=LICENSED_USES,
        license_summary="expired",
        license_expiry="2020-01-01T00:00:00Z",
    )
    with pytest.raises(PermittedUseDeniedError, match="license_expired"):
        rights_stack.rights.require_permitted_use(source.source_id, PermittedUse.CITATION)


def test_unknown_source_fail_closed(rights_stack) -> None:
    with pytest.raises(SourceNotFoundError):
        rights_stack.rights.get_source(
            "src_missing", principal=rights_stack.principal, acl_epoch=rights_stack.epoch
        )


def test_owner_export_disclosure_includes_license_and_validation(
    rights_stack, licensed_source
) -> None:
    source = licensed_source
    disclosure = rights_stack.rights.export_source_disclosure(
        source.source_id, principal=rights_stack.principal, acl_epoch=rights_stack.epoch
    )
    payload = disclosure.to_dict()
    assert payload["license_summary"] == "licensed for citation and generation"
    assert payload["validation_state"] == SourceValidationState.VALIDATED.value
    assert payload["validated_by"] == rights_stack.owner.id
    assert "chain_of_thought" not in payload


def test_rights_use_workspace_meta_without_new_tables(rights_stack) -> None:
    before = {
        str(row["name"])
        for row in rights_stack.workspace.store.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    register_source = rights_stack.rights.register_source
    register_source(
        project_id=rights_stack.project.id,
        title="Storage probe corpus",
        classification=SourceClassification.LICENSED,
        principal=rights_stack.principal,
        acl_epoch=rights_stack.epoch,
        permitted_uses=LICENSED_USES,
        license_summary="licensed for citation and generation",
        license_expiry="2099-01-01T00:00:00Z",
    )
    after = {
        str(row["name"])
        for row in rights_stack.workspace.store.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert after == before
    digest = rights_stack.workspace.store.get_meta("rights.index_digest")
    assert digest is not None
    assert rights_stack.workspace.store.blobs.exists(digest)


def test_offline_registry_needs_no_network(rights_stack) -> None:
    rights_stack.workspace.set_airplane_mode(True)
    rights_stack.workspace.set_outage("auth_outage", True)
    source = rights_stack.rights.register_source(
        project_id=rights_stack.project.id,
        title="Offline corpus",
        classification=SourceClassification.LICENSED,
        principal=rights_stack.principal,
        acl_epoch=rights_stack.epoch,
        permitted_uses=LICENSED_USES,
        license_summary="licensed for citation and generation",
        license_expiry="2099-01-01T00:00:00Z",
    )
    assert rights_stack.rights.require_permitted_use(
        source.source_id, PermittedUse.CITATION
    ).allowed
    listed = rights_stack.rights.list_sources(
        rights_stack.project.id,
        principal=rights_stack.principal,
        acl_epoch=rights_stack.epoch,
    )
    assert listed[0].source_id == source.source_id
