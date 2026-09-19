"""Deterministic ScreenplayDocument AST dumps and structural facts."""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any

from movie_muse.document.api import normalize, semantic_validate
from movie_muse.persistence.api import digest_payload
from movie_muse.schemas.api import (
    BlockKind,
    ScreenplayDocument,
    StructuralFact,
    new_ulid,
)
from movie_muse.testkit.ids import FIXED_TIME_MS

AST_EXTRACTOR_VERSION = "document_kernel/1.0"


def _fact_id(document_id: str, attribute: str) -> str:
    digest = hashlib.sha256(f"{document_id}:{attribute}".encode()).digest()[:10]
    return f"fcs_{new_ulid(_time_ms=FIXED_TIME_MS, _random_bytes=digest)}"


def derive_structural_facts(document: ScreenplayDocument) -> tuple[StructuralFact, ...]:
    """Deterministic structural facts from the typed document kernel. Not FilmIR."""

    counts = Counter(block.kind.value for block in document.blocks)
    scene_numbers = tuple(
        block.scene_number
        for block in document.blocks
        if block.kind is BlockKind.SCENE_HEADING and block.scene_number
    )
    scene_ids = tuple(
        block.scene_id
        for block in document.blocks
        if block.kind is BlockKind.SCENE_HEADING and block.scene_id
    )
    dual_groups = tuple(
        sorted(
            {
                block.dual_dialogue_group_id
                for block in document.blocks
                if block.is_dual_dialogue and block.dual_dialogue_group_id
            }
        )
    )
    unknown_keys = tuple(
        sorted(
            {
                str(key)
                for block in document.blocks
                for key in block.unknown_extensions
            }
        )
    )
    boneyard = tuple(block.id for block in document.blocks if block.is_boneyard)
    revision_id = document.base_revision_id or document.id
    specs: tuple[tuple[str, Any], ...] = (
        ("title", document.title),
        ("block_kind_counts", dict(sorted(counts.items()))),
        ("scene_numbers", list(scene_numbers)),
        ("scene_ids", list(scene_ids)),
        ("dual_dialogue_groups", list(dual_groups)),
        ("note_ids", [note.id for note in document.notes]),
        ("production_tag_ids", [tag.id for tag in document.production_tags]),
        ("revision_mark_ids", [mark.id for mark in document.revision_marks]),
        ("unknown_extension_keys", list(unknown_keys)),
        ("boneyard_block_ids", list(boneyard)),
        ("block_count", len(document.blocks)),
    )
    facts: list[StructuralFact] = []
    for attribute, value in specs:
        facts.append(
            StructuralFact(
                id=_fact_id(document.id, attribute),
                subject_id=document.id,
                attribute=attribute,
                value=value,
                derived_from_revision_id=revision_id,
                extractor_version=AST_EXTRACTOR_VERSION,
            )
        )
    return tuple(facts)


def dump_ast(document: ScreenplayDocument) -> dict[str, Any]:
    normalized = normalize(document)
    semantic_validate(normalized)
    facts = derive_structural_facts(normalized)
    return {
        "kind": "ast",
        "status": "current",
        "producer": "document_kernel",
        "awaiting": None,
        "schema_version": "1.0",
        "payload": {
            "document": normalized.to_dict(),
            "structural_facts": [fact.to_dict() for fact in facts],
        },
        "note": None,
    }


def ast_digest(document: ScreenplayDocument) -> str:
    _, digest = digest_payload(dump_ast(document))
    return digest
