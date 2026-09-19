"""Reference Lens surfaces permitted sources with citations, not training memory."""

from __future__ import annotations

import pytest

from movie_muse.reference_lens.api import LensDisabledError, TrainingMemoryClaimError
from movie_muse.rights.api import PermittedUse, SourceClassification, UnlicensedSourceError

LICENSED_USES = (
    PermittedUse.RETRIEVAL,
    PermittedUse.CITATION,
    PermittedUse.GENERATION,
    PermittedUse.EXPORT_DISCLOSURE,
)


def _index_licensed(stack, *, title: str, text: str, summary: str):
    source = stack.rights.register_source(
        project_id=stack.project.id,
        title=title,
        classification=SourceClassification.LICENSED,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        permitted_uses=LICENSED_USES,
        license_summary=summary,
        license_expiry="2099-01-01T00:00:00Z",
    )
    stack.retrieval.index_reference(
        source_id=source.source_id,
        text=text,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        project_id=stack.project.id,
        title=title,
    )
    return source


def test_query_explains_similarity_rights_and_counter_reference(lens_stack) -> None:
    primary = _index_licensed(
        lens_stack,
        title="Kitchen lock notes",
        text="The pantry lock is brass and sticks in humidity.",
        summary="licensed kitchen research",
    )
    _index_licensed(
        lens_stack,
        title="Harbor tide memo",
        text="Harbor tide tables for the night shoot near the lock.",
        summary="licensed production memo",
    )
    hits = lens_stack.lens.query(
        project_id=lens_stack.project.id,
        query="pantry lock humidity",
        principal=lens_stack.principal,
        acl_epoch=lens_stack.epoch,
    )
    assert hits
    hit = hits[0]
    assert hit.source_id == primary.source_id
    assert "token overlap" in hit.similarity
    assert "brass" in hit.relevant_passage
    assert hit.structure_note
    assert hit.difference
    assert hit.rights.classification is SourceClassification.LICENSED
    assert hit.rights.license_summary == "licensed kitchen research"
    assert hit.citation.source_id == primary.source_id
    assert hit.citation.rights_record_id == primary.rights_record_id
    assert "registry lookup" in hit.why_surfaced.lower()
    assert "model training memory" not in hit.why_surfaced.lower()
    resolved = lens_stack.lens.resolve_citation(
        hit.citation, principal=lens_stack.principal, acl_epoch=lens_stack.epoch
    )
    assert resolved.id == hit.citation.source_version_id
    assert hit.counter_reference is not None
    assert hit.counter_reference.source_id != hit.source_id


def test_unlicensed_source_cannot_surface(lens_stack) -> None:
    source = lens_stack.rights.register_source(
        project_id=lens_stack.project.id,
        title="Scraped dump",
        classification=SourceClassification.UNLICENSED,
        principal=lens_stack.principal,
        acl_epoch=lens_stack.epoch,
        permitted_uses=(),
    )
    with pytest.raises(UnlicensedSourceError):
        lens_stack.retrieval.index_reference(
            source_id=source.source_id,
            text="stolen pages about the pantry lock",
            principal=lens_stack.principal,
            acl_epoch=lens_stack.epoch,
            project_id=lens_stack.project.id,
        )


def test_training_memory_queries_fail_closed(lens_stack) -> None:
    with pytest.raises(TrainingMemoryClaimError):
        lens_stack.lens.query(
            project_id=lens_stack.project.id,
            query="what did the model training memory retain about locks",
            principal=lens_stack.principal,
            acl_epoch=lens_stack.epoch,
        )


def test_disable_and_delete_local_indexes(lens_stack) -> None:
    _index_licensed(
        lens_stack,
        title="Kitchen lock notes",
        text="The pantry lock is brass and sticks in humidity.",
        summary="licensed kitchen research",
    )
    lens_stack.lens.disable(
        lens_stack.project.id,
        principal=lens_stack.principal,
        acl_epoch=lens_stack.epoch,
    )
    with pytest.raises(LensDisabledError):
        lens_stack.lens.query(
            project_id=lens_stack.project.id,
            query="pantry lock",
            principal=lens_stack.principal,
            acl_epoch=lens_stack.epoch,
        )
    lens_stack.lens.enable(
        lens_stack.project.id,
        principal=lens_stack.principal,
        acl_epoch=lens_stack.epoch,
    )
    before = lens_stack.lens.query(
        project_id=lens_stack.project.id,
        query="pantry lock",
        principal=lens_stack.principal,
        acl_epoch=lens_stack.epoch,
    )
    assert before
    lens_stack.lens.delete_local_indexes(
        lens_stack.project.id,
        principal=lens_stack.principal,
        acl_epoch=lens_stack.epoch,
    )
    after = lens_stack.lens.query(
        project_id=lens_stack.project.id,
        query="pantry lock",
        principal=lens_stack.principal,
        acl_epoch=lens_stack.epoch,
    )
    assert after == ()
