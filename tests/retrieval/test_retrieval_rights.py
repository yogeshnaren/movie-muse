"""Rights-controlled retrieval fails closed on unlicensed or uncited sources."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import Role
from movie_muse.rights.api import (
    PermittedUse,
    PermittedUseDeniedError,
    SourceClassification,
    UnlicensedSourceError,
)


def test_licensed_source_retrieves_with_citations(retrieval_stack, licensed_source) -> None:
    retrieval_stack.retrieval.index_reference(
        source_id=licensed_source.source_id,
        text="The pantry lock is brass and sticks in humidity.",
        principal=retrieval_stack.principal,
        acl_epoch=retrieval_stack.epoch,
        project_id=retrieval_stack.project.id,
    )
    hits = retrieval_stack.retrieval.retrieve(
        project_id=retrieval_stack.project.id,
        query="pantry lock humidity",
        principal=retrieval_stack.principal,
        acl_epoch=retrieval_stack.epoch,
    )
    assert len(hits) == 1
    hit = hits[0]
    assert hit.project_id == retrieval_stack.project.id
    assert hit.source_id == licensed_source.source_id
    assert hit.citation.source_id == licensed_source.source_id
    assert hit.citation.rights_record_id == licensed_source.rights_record_id
    assert hit.citation.source_version_id
    assert hit.untrusted is True
    assert licensed_source.source_id in hit.source_ids


def test_unlicensed_source_cannot_be_indexed_or_retrieved(retrieval_stack) -> None:
    source = retrieval_stack.rights.register_source(
        project_id=retrieval_stack.project.id,
        title="Scraped dump",
        classification=SourceClassification.UNLICENSED,
        principal=retrieval_stack.principal,
        acl_epoch=retrieval_stack.epoch,
        permitted_uses=(),
    )
    with pytest.raises(UnlicensedSourceError):
        retrieval_stack.retrieval.index_reference(
            source_id=source.source_id,
            text="stolen pages",
            principal=retrieval_stack.principal,
            acl_epoch=retrieval_stack.epoch,
            project_id=retrieval_stack.project.id,
        )


def test_source_without_citation_use_fails_closed(retrieval_stack) -> None:
    source = retrieval_stack.rights.register_source(
        project_id=retrieval_stack.project.id,
        title="Retrieval-only memo",
        classification=SourceClassification.LICENSED,
        principal=retrieval_stack.principal,
        acl_epoch=retrieval_stack.epoch,
        permitted_uses=(PermittedUse.RETRIEVAL,),
        license_summary="retrieval without citation",
        license_expiry="2099-01-01T00:00:00Z",
    )
    retrieval_stack.retrieval.index_reference(
        source_id=source.source_id,
        text="Harbor tide tables for the night shoot.",
        principal=retrieval_stack.principal,
        acl_epoch=retrieval_stack.epoch,
        project_id=retrieval_stack.project.id,
    )
    with pytest.raises(PermittedUseDeniedError):
        retrieval_stack.retrieval.retrieve(
            project_id=retrieval_stack.project.id,
            query="harbor tide",
            principal=retrieval_stack.principal,
            acl_epoch=retrieval_stack.epoch,
        )


def test_revoked_license_fails_on_later_retrieve(retrieval_stack, licensed_source) -> None:
    retrieval_stack.retrieval.index_reference(
        source_id=licensed_source.source_id,
        text="Brass pantry lock notes.",
        principal=retrieval_stack.principal,
        acl_epoch=retrieval_stack.epoch,
        project_id=retrieval_stack.project.id,
    )
    retrieval_stack.rights.update_source(
        licensed_source.source_id,
        principal=retrieval_stack.principal,
        acl_epoch=retrieval_stack.epoch,
        classification=SourceClassification.UNLICENSED,
        permitted_uses=(),
    )
    with pytest.raises(UnlicensedSourceError):
        retrieval_stack.retrieval.retrieve(
            project_id=retrieval_stack.project.id,
            query="pantry lock",
            principal=retrieval_stack.principal,
            acl_epoch=retrieval_stack.epoch,
        )


def test_viewer_can_retrieve_but_cannot_index(
    retrieval_stack, licensed_source, member
) -> None:
    retrieval_stack.retrieval.index_reference(
        source_id=licensed_source.source_id,
        text="Ada prefers silence in the kitchen.",
        principal=retrieval_stack.principal,
        acl_epoch=retrieval_stack.epoch,
        project_id=retrieval_stack.project.id,
    )
    viewer = member(Role.VIEWER)
    hits = retrieval_stack.retrieval.retrieve(
        project_id=retrieval_stack.project.id,
        query="kitchen silence",
        principal=viewer,
        acl_epoch=retrieval_stack.epoch,
    )
    assert len(hits) == 1
    with pytest.raises(AuthorizationError):
        retrieval_stack.retrieval.index_reference(
            source_id=licensed_source.source_id,
            text="viewer must not index",
            principal=viewer,
            acl_epoch=retrieval_stack.epoch,
            project_id=retrieval_stack.project.id,
        )
