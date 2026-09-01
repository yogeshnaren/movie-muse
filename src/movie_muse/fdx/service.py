"""FDX profile validation, lossless adapters, and lossy import pathways."""

from __future__ import annotations

import hashlib
from pathlib import Path

from movie_muse.document.api import normalize, semantic_validate, structural_diff
from movie_muse.fdx.convert import export_fdx, import_fdx, validate_profile
from movie_muse.fdx.errors import SilentLossError
from movie_muse.fdx.final_draft import (
    final_draft_available,
    final_draft_round_trip,
    import_pdf,
    require_final_draft,
)
from movie_muse.fdx.fountain import import_fountain, import_plain_text
from movie_muse.fdx.serialize import parse_xml
from movie_muse.fdx.types import PROFILE_NAME, PROFILE_VERSION, LossReport
from movie_muse.schemas.api import OperationType, ScreenplayDocument


class FdxService:
    """Public adapter: ScreenplayDocument is canonical; FDX is a compatibility format."""

    profile_name = PROFILE_NAME
    profile_version = PROFILE_VERSION

    def export_document(self, document: ScreenplayDocument) -> bytes:
        semantic_validate(normalize(document))
        return export_fdx(document)

    def import_bytes(self, data: bytes | str) -> tuple[ScreenplayDocument, LossReport]:
        return import_fdx(data)

    def import_path(self, path: Path | str) -> tuple[ScreenplayDocument, LossReport]:
        payload = Path(path).read_bytes()
        return import_fdx(payload)

    def validate(self, data: bytes | str) -> None:
        validate_profile(parse_xml(data))

    def export_digest(self, document: ScreenplayDocument) -> str:
        return hashlib.sha256(self.export_document(document)).hexdigest()

    def round_trip(self, document: ScreenplayDocument) -> tuple[ScreenplayDocument, LossReport, str]:
        exported = self.export_document(document)
        imported, report = self.import_bytes(exported)
        if self.export_digest(document) != self.export_digest(imported):
            raise SilentLossError("FDX re-export digest changed after import; conversion is not deterministic")
        return imported, report, self.export_digest(document)

    def assert_lossless(self, original: ScreenplayDocument, imported: ScreenplayDocument) -> None:
        source = normalize(original)
        target = normalize(imported)
        diff = structural_diff(
            source,
            target,
            author_actor_id="act_fdx_round_trip",
            created_at="2026-09-01T00:00:00Z",
            base_revision_id=source.base_revision_id,
        )
        source_ids = [block.id for block in source.blocks]
        target_ids = [block.id for block in target.blocks]
        operations = list(diff.operations)
        if source_ids == target_ids:
            # structural_diff always emits MOVE_BLOCK as a replay recipe even when
            # order is unchanged. Unchanged order is not loss.
            operations = [op for op in operations if op.op_type is not OperationType.MOVE_BLOCK]
        if operations:
            raise SilentLossError(
                "FDX round trip changed typed structure: "
                + ",".join(op.op_type.value for op in operations)
            )
        if _semantic_snapshot(source) != _semantic_snapshot(target):
            raise SilentLossError("FDX round trip lost text, scene, note, tag, revision, or lock data")

    def import_fountain(self, text: str) -> tuple[ScreenplayDocument, LossReport]:
        document, report = import_fountain(text)
        if report.lossless:
            raise SilentLossError("Fountain import must disclose loss; empty LossReport is forbidden")
        return document, report

    def import_plain_text(self, text: str) -> tuple[ScreenplayDocument, LossReport]:
        document, report = import_plain_text(text)
        if report.lossless:
            raise SilentLossError("plain-text import must disclose loss; empty LossReport is forbidden")
        return document, report

    def import_pdf(self, data: bytes) -> None:
        import_pdf(data)

    def final_draft_available(self) -> bool:
        return final_draft_available()

    def require_final_draft(self) -> str:
        return require_final_draft()

    def final_draft_round_trip(self, document: ScreenplayDocument) -> bytes:
        return final_draft_round_trip(document)


def _semantic_snapshot(document: ScreenplayDocument) -> tuple[object, ...]:
    return (
        document.id,
        document.project_id,
        document.title,
        document.paper_size,
        document.style,
        document.schema_version,
        document.base_revision_id,
        tuple((seq.id, seq.title, seq.order, seq.scene_ids) for seq in document.sequences),
        tuple(
            (
                block.id,
                block.kind.value,
                block.text,
                tuple(
                    (span.id, span.start_offset, span.end_offset, span.span_kind, span.ref_id)
                    for span in block.spans
                ),
                block.scene_id,
                block.scene_number,
                block.character_cue_id,
                block.dialogue_pair_id,
                block.is_dual_dialogue,
                block.dual_dialogue_group_id,
                block.is_forced,
                block.is_continued,
                block.is_extension,
                block.is_boneyard,
                block.note_ids,
                block.revision_mark_ids,
                block.production_tag_ids,
                block.attachment_ids,
                tuple(sorted(block.unknown_extensions.items(), key=lambda item: item[0])),
            )
            for block in document.blocks
        ),
        tuple(
            (note.id, note.block_id, note.author_actor_id, note.text, note.resolved)
            for note in document.notes
        ),
        tuple(
            (mark.id, mark.block_id, mark.revision_color, mark.revision_label)
            for mark in document.revision_marks
        ),
        tuple(
            (tag.id, tag.block_id, tag.department, tag.tag_type, tag.value)
            for tag in document.production_tags
        ),
        tuple(
            (att.id, att.kind, att.uri, att.checksum, att.block_id)
            for att in document.attachments
        ),
    )
