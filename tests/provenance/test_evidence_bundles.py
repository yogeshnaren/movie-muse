"""Evidence Bundle construction, citations, lineage, and validation."""

from __future__ import annotations

import pytest

from movie_muse.artifacts.api import ArtifactClassification, ArtifactType
from movie_muse.identity.api import Role
from movie_muse.provenance.api import (
    ChainOfThoughtRejectedError,
    CitationInput,
    HumanValidationError,
    HumanValidationState,
    InputLineage,
    MethodProvenance,
    MissingCitationError,
)
from movie_muse.rights.api import (
    PermittedUse,
    PermittedUseDeniedError,
    SourceClassification,
    UnlicensedSourceError,
)
from movie_muse.schemas.api import ArtifactStatus

LICENSED_USES = (
    PermittedUse.RETRIEVAL,
    PermittedUse.CITATION,
    PermittedUse.GENERATION,
    PermittedUse.FORECAST,
    PermittedUse.EXPORT_DISCLOSURE,
)


def sample_provenance() -> MethodProvenance:
    return MethodProvenance(
        provider="deterministic-double",
        model="fixture-extractor",
        model_version="1.0.0",
        prompt_version="1.0.0",
        policy_version="1.0.0",
        timestamp="2026-09-01T16:00:00Z",
        prompt_id="prompt.extract",
        method="structured extraction",
    )


def test_missing_citation_is_blocked(provenance_stack) -> None:
    with pytest.raises(MissingCitationError):
        provenance_stack.provenance.build_bundle(
            project_id=provenance_stack.project.id,
            claim="The scene needs rain.",
            method_summary="Heuristic weather inference",
            provenance=sample_provenance(),
            principal=provenance_stack.principal,
            acl_epoch=provenance_stack.epoch,
            citations=(),
        )


def test_unlicensed_citation_is_blocked(provenance_stack) -> None:
    unlicensed = provenance_stack.rights.register_source(
        project_id=provenance_stack.project.id,
        title="Unlicensed scrape",
        classification=SourceClassification.UNLICENSED,
        principal=provenance_stack.principal,
        acl_epoch=provenance_stack.epoch,
    )
    with pytest.raises(UnlicensedSourceError):
        provenance_stack.provenance.build_bundle(
            project_id=provenance_stack.project.id,
            claim="Use the scrape as proof.",
            method_summary="Citation of an unlicensed dump",
            provenance=sample_provenance(),
            principal=provenance_stack.principal,
            acl_epoch=provenance_stack.epoch,
            citations=(
                CitationInput(source_id=unlicensed.source_id, excerpt_summary="stolen pages"),
            ),
        )


def test_chain_of_thought_is_rejected(provenance_stack, licensed_source) -> None:
    source = licensed_source
    with pytest.raises(ChainOfThoughtRejectedError):
        provenance_stack.provenance.build_bundle(
            project_id=provenance_stack.project.id,
            claim="Recommend a night exterior.",
            method_summary="Private chain_of_thought leaked here",
            provenance=sample_provenance(),
            principal=provenance_stack.principal,
            acl_epoch=provenance_stack.epoch,
            citations=(CitationInput(source_id=source.source_id, excerpt_summary="night notes"),),
        )
    with pytest.raises(ChainOfThoughtRejectedError):
        provenance_stack.provenance.build_bundle(
            project_id=provenance_stack.project.id,
            claim="Recommend a night exterior.",
            method_summary="Deterministic layout comparison",
            provenance={
                **sample_provenance().to_dict(),
                "chain_of_thought": "hidden reasoning",
            },
            principal=provenance_stack.principal,
            acl_epoch=provenance_stack.epoch,
            citations=(CitationInput(source_id=source.source_id, excerpt_summary="night notes"),),
        )


def test_bundle_links_permitted_evidence_and_model_provenance(
    provenance_stack, licensed_source
) -> None:
    source = licensed_source
    revision_id = provenance_stack.revisions.canon_head_id()
    stored = provenance_stack.provenance.build_bundle(
        project_id=provenance_stack.project.id,
        claim="Keep the archive location.",
        method_summary="Compare licensed notes to the current scene heading",
        provenance=sample_provenance(),
        principal=provenance_stack.principal,
        acl_epoch=provenance_stack.epoch,
        citations=(
            CitationInput(source_id=source.source_id, excerpt_summary="archive is load-bearing"),
        ),
        cited_node_ids=(provenance_stack.document.blocks[0].id,),
        assumptions=("The registered stills remain licensed.",),
        alternatives=("Relocate to a constructed interior.",),
        counter_evidence=("A later memo prefers a soundstage.",),
        sensitivity="location change would ripple schedule",
        confidence=0.72,
        uncertainty="medium; one licensed stills pack",
        revision_ids=(revision_id,),
        lineage=InputLineage(source_ids=(source.source_id,)),
    )
    view = stored.public_view()
    assert stored.bundle.cited_sources[0].source_id == source.source_id
    assert stored.bundle.cited_sources[0].rights_record_id == source.rights_record_id
    assert stored.method_provenance.provider == "deterministic-double"
    assert stored.method_provenance.model_version == "1.0.0"
    assert stored.method_provenance.prompt_version == "1.0.0"
    assert stored.method_provenance.policy_version == "1.0.0"
    assert revision_id in stored.lineage.revision_ids
    assert source.source_id in stored.lineage.source_ids
    assert stored.bundle.human_validation_state is HumanValidationState.UNREVIEWED
    assert "chain_of_thought" not in view
    assert view["uncertainty"] == "medium; one licensed stills pack"
    assert view["counter_evidence"] == ["A later memo prefers a soundstage."]
    assert view["rights_license"]


def test_candidate_integration_source_cannot_be_cited_until_validated(
    provenance_stack, member
) -> None:
    bot = member(Role.INTEGRATION_SERVICE, integration=True)
    candidate = provenance_stack.rights.register_source(
        project_id=provenance_stack.project.id,
        title="Vendor ingest",
        classification=SourceClassification.LICENSED,
        principal=bot,
        acl_epoch=provenance_stack.epoch,
        permitted_uses=LICENSED_USES,
        license_summary="vendor license",
    )
    with pytest.raises(PermittedUseDeniedError):
        provenance_stack.provenance.build_bundle(
            project_id=provenance_stack.project.id,
            claim="Use the vendor pack.",
            method_summary="Cite vendor ingest",
            provenance=sample_provenance(),
            principal=provenance_stack.principal,
            acl_epoch=provenance_stack.epoch,
            citations=(CitationInput(source_id=candidate.source_id, excerpt_summary="vendor still"),),
        )
    provenance_stack.rights.validate_source(
        candidate.source_id,
        principal=provenance_stack.principal,
        acl_epoch=provenance_stack.epoch,
    )
    stored = provenance_stack.provenance.build_bundle(
        project_id=provenance_stack.project.id,
        claim="Use the vendor pack after review.",
        method_summary="Cite human-validated vendor ingest",
        provenance=sample_provenance(),
        principal=bot,
        acl_epoch=provenance_stack.epoch,
        citations=(CitationInput(source_id=candidate.source_id, excerpt_summary="vendor still"),),
    )
    assert stored.created_by == bot.actor_id
    with pytest.raises(HumanValidationError):
        provenance_stack.provenance.validate_bundle(
            stored.bundle.id, principal=bot, acl_epoch=provenance_stack.epoch
        )
    validated = provenance_stack.provenance.validate_bundle(
        stored.bundle.id,
        principal=provenance_stack.principal,
        acl_epoch=provenance_stack.epoch,
    )
    assert validated.bundle.human_validation_state is HumanValidationState.ACCEPTED
    assert validated.validated_by == provenance_stack.owner.id
    assert validated.validated_at is not None


def test_bundle_can_link_to_generic_artifact_version(provenance_stack, licensed_source) -> None:
    source = licensed_source
    stored = provenance_stack.provenance.build_bundle(
        project_id=provenance_stack.project.id,
        claim="Package the licensed stills.",
        method_summary="Render a disclosure packet from permitted sources",
        provenance=sample_provenance(),
        principal=provenance_stack.principal,
        acl_epoch=provenance_stack.epoch,
        citations=(CitationInput(source_id=source.source_id, excerpt_summary="stills log"),),
    )
    template = provenance_stack.artifacts.register_template(
        project_id=provenance_stack.project.id,
        version="1.0",
        renderer_version="deterministic-json/1",
        body="evidence disclosure",
        principal=provenance_stack.principal,
        acl_epoch=provenance_stack.epoch,
    )
    artifact = provenance_stack.artifacts.create_artifact(
        project_id=provenance_stack.project.id,
        artifact_type=ArtifactType.PACKAGE,
        title="Evidence disclosure packet",
        principal=provenance_stack.principal,
        acl_epoch=provenance_stack.epoch,
    )
    version = provenance_stack.artifacts.create_version(
        artifact.id,
        inputs={"bundle_id": stored.bundle.id},
        source_revision_id=provenance_stack.revisions.canon_head_id(),
        template_id=template.id,
        template_version=template.version,
        renderer_version=template.renderer_version,
        classification=ArtifactClassification.INTERNAL,
        principal=provenance_stack.principal,
        acl_epoch=provenance_stack.epoch,
        evidence_bundle_ids=(stored.bundle.id,),
        rights_record_ids=(source.rights_record_id or "",)
    )
    assert version.status is ArtifactStatus.DRAFT
    links = provenance_stack.provenance.attach_artifact_version(
        stored.bundle.id,
        version.version.id,
        principal=provenance_stack.principal,
        acl_epoch=provenance_stack.epoch,
    )
    assert version.version.id in links
    assert provenance_stack.provenance.list_artifact_links(stored.bundle.id) == links
