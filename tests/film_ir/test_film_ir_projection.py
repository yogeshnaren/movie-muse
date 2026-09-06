"""Deterministic FilmIR from the compiler; reprocessing is idempotent."""

from __future__ import annotations

from movie_muse.film_ir.api import EXTRACTOR_VERSION
from movie_muse.schemas.api import EpistemicLevel
from movie_muse.testkit.api import FixtureCatalog


def test_project_is_idempotent_and_structural(film_ir_stack) -> None:
    first = film_ir_stack.film_ir.project(
        film_ir_stack.document,
        principal=film_ir_stack.principal,
        acl_epoch=film_ir_stack.epoch,
    )
    second = film_ir_stack.film_ir.project(
        film_ir_stack.document,
        principal=film_ir_stack.principal,
        acl_epoch=film_ir_stack.epoch,
    )
    assert first.id == second.id
    assert first.extractor_version == EXTRACTOR_VERSION
    assert first.source_revision_id == film_ir_stack.document.base_revision_id
    loaded = film_ir_stack.film_ir.get_for_revision(first.source_revision_id)
    assert loaded.id == first.id
    kinds = {entity.kind.value for entity in first.entities}
    assert "character" in kinds
    assert "location" in kinds
    names = {entity.canonical_name for entity in first.entities if entity.kind.value == "character"}
    assert "ADA" in names
    compiled = film_ir_stack.compiler.compile(film_ir_stack.document)
    scores = film_ir_stack.film_ir.score(first, compiled)
    assert scores.meets(min_precision=1.0, min_recall=1.0)


def test_small_kitchen_precision_recall_against_compiler() -> None:
    from movie_muse.compiler.api import CompilerService
    from movie_muse.film_ir.api import EXTRACTOR_VERSION, score_against_compiler
    from movie_muse.persistence.api import utc_now
    from movie_muse.schemas.api import FilmIR, FilmIrEntity, FilmIrEntityKind

    document = FixtureCatalog().get("small_kitchen").document
    compiled = CompilerService().compile(document)
    kind_map = {
        "character": FilmIrEntityKind.CHARACTER,
        "location": FilmIrEntityKind.LOCATION,
        "prop": FilmIrEntityKind.PROP,
        "scene": FilmIrEntityKind.SCENE,
    }
    film_ir = FilmIR(
        id="fir_small_kitchen_score",
        project_id=document.project_id,
        source_revision_id=compiled.source_revision_id,
        extractor_version=EXTRACTOR_VERSION,
        computed_at=utc_now(),
        entities=tuple(
            FilmIrEntity(
                id=f"firent_{index}",
                kind=kind_map[entity.kind],
                canonical_name=entity.canonical_name,
                scene_ids=entity.scene_ids,
                mention_block_ids=entity.mention_block_ids,
            )
            for index, entity in enumerate(compiled.entities)
            if entity.kind in kind_map
        ),
        scene_order=compiled.scene_order,
    )
    scores = score_against_compiler(film_ir, compiled)
    assert scores.meets(min_precision=0.95, min_recall=0.95)


def test_extraction_candidates_are_inferred_not_authored(film_ir_stack) -> None:
    projection = film_ir_stack.film_ir.extract_candidates(
        film_ir_stack.document,
        principal=film_ir_stack.principal,
        acl_epoch=film_ir_stack.epoch,
        permission_snapshot_id=film_ir_stack.snapshot,
    )
    structural = {
        entity.canonical_name.casefold() for entity in projection.film_ir.entities
    }
    assert projection.candidates is not None
    assert projection.candidates.raw_entities
    for claim in projection.candidates.claims:
        assert claim.kind is EpistemicLevel.INFERRED
        assert str(claim.value).casefold() not in structural
