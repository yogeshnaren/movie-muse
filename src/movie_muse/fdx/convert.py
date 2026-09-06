"""ScreenplayDocument ↔ Movie Muse FDX profile conversion."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from xml.etree import ElementTree as ET

from movie_muse.document.api import normalize, semantic_validate
from movie_muse.fdx.errors import FdxParseError, FdxProfileError
from movie_muse.fdx.serialize import (
    append,
    canonical_xml,
    dump_json_attr,
    elem,
    jsonable,
    load_json_attr,
    local_name,
    namespace_of,
    parse_xml,
    qname,
)
from movie_muse.fdx.types import (
    ALLOWED_PARAGRAPH_TYPES,
    DOCUMENT_TYPE,
    FDX_VERSION,
    KIND_TO_PARAGRAPH,
    MM_NS,
    PARAGRAPH_TO_KIND,
    PROFILE_NAME,
    PROFILE_VERSION,
    TEMPLATE_NAME,
    LossAccumulator,
    LossReport,
    LossSeverity,
)
from movie_muse.schemas.api import (
    Attachment,
    Block,
    BlockKind,
    InlineSpan,
    Note,
    ProductionTag,
    RevisionMark,
    ScreenplayDocument,
    Sequence,
    new_id,
)

BOOL_ATTRS = ("is_dual_dialogue", "is_forced", "is_continued", "is_extension", "is_boneyard")


def export_fdx(document: ScreenplayDocument) -> bytes:
    normalized = normalize(document)
    semantic_validate(normalized)
    root = elem(
        "FinalDraft",
        attrib={
            "DocumentType": DOCUMENT_TYPE,
            "Template": TEMPLATE_NAME,
            "Version": FDX_VERSION,
            "xmlns:mm": MM_NS,
        },
    )
    content = append(root, elem("Content"))
    title_page = append(root, elem("TitlePage"))
    for block in normalized.blocks:
        if block.kind is BlockKind.TITLE_PAGE_ELEMENT:
            append(title_page, _paragraph(block))
        append(content, _paragraph(block))
    meta = append(root, elem(qname("Document")))
    meta.set("id", normalized.id)
    meta.set("project-id", normalized.project_id)
    meta.set("title", normalized.title)
    meta.set("paper-size", normalized.paper_size)
    meta.set("style", normalized.style)
    if normalized.base_revision_id:
        meta.set("base-revision-id", normalized.base_revision_id)
    meta.set("schema-version", normalized.schema_version)
    meta.set("profile", PROFILE_NAME)
    meta.set("profile-version", PROFILE_VERSION)
    sequences = append(root, elem(qname("Sequences")))
    for sequence in normalized.sequences:
        node = append(
            sequences,
            elem(
                qname("Sequence"),
                attrib={
                    "id": sequence.id,
                    "title": sequence.title,
                    "order": str(sequence.order),
                    "schema-version": sequence.schema_version,
                },
            ),
        )
        for scene_id in sequence.scene_ids:
            append(node, elem(qname("SceneRef"), attrib={"id": scene_id}))
    notes = append(root, elem(qname("Notes")))
    for note in normalized.notes:
        child = append(
            notes,
            elem(
                qname("Note"),
                text=note.text,
                attrib={
                    "id": note.id,
                    "block-id": note.block_id,
                    "author-actor-id": note.author_actor_id,
                    "created-at": note.created_at,
                    "resolved": "true" if note.resolved else "false",
                    "schema-version": note.schema_version,
                },
            ),
        )
        child.text = note.text
    marks = append(root, elem(qname("RevisionMarks")))
    for mark in normalized.revision_marks:
        append(
            marks,
            elem(
                qname("RevisionMark"),
                attrib={
                    "id": mark.id,
                    "block-id": mark.block_id,
                    "revision-color": mark.revision_color,
                    "revision-label": mark.revision_label,
                    "created-at": mark.created_at,
                    "schema-version": mark.schema_version,
                },
            ),
        )
    tags = append(root, elem(qname("ProductionTags")))
    for tag in normalized.production_tags:
        append(
            tags,
            elem(
                qname("ProductionTag"),
                attrib={
                    "id": tag.id,
                    "block-id": tag.block_id,
                    "department": tag.department,
                    "tag-type": tag.tag_type,
                    "value": tag.value,
                    "schema-version": tag.schema_version,
                },
            ),
        )
    attachments = append(root, elem(qname("Attachments")))
    for attachment in normalized.attachments:
        attrib = {
            "id": attachment.id,
            "kind": attachment.kind,
            "uri": attachment.uri,
            "checksum": attachment.checksum,
            "schema-version": attachment.schema_version,
        }
        if attachment.block_id:
            attrib["block-id"] = attachment.block_id
        append(attachments, elem(qname("Attachment"), attrib=attrib))
    return canonical_xml(root)


def import_fdx(data: bytes | str) -> tuple[ScreenplayDocument, LossReport]:
    try:
        root = parse_xml(data)
    except ET.ParseError as exc:
        raise FdxParseError(str(exc)) from exc
    losses = LossAccumulator(pathway="fdx")
    validate_profile(root, losses)
    meta = _first(root, qname("Document"))
    project_id = _attr(meta, "project-id") or new_id("project")
    doc_id = _attr(meta, "id") or new_id("document")
    title = _attr(meta, "title") or "Untitled"
    if meta is None:
        losses.add("minted_metadata", "FDX had no mm:Document; ids and title were minted")
    content = _first(root, "Content")
    if content is None:
        raise FdxProfileError("FDX document is missing Content")
    blocks: list[Block] = []
    seen_ids: set[str] = set()
    title_page = _first(root, "TitlePage")
    if title_page is None:
        title_page = _first(content, "TitlePage")
    for child in list(content):
        if local_name(child.tag) == "TitlePage":
            continue
        if local_name(child.tag) != "Paragraph":
            _preserve_unknown(child, losses, path="Content")
            continue
        block = _block_from_paragraph(child, losses)
        blocks.append(block)
        seen_ids.add(block.id)
    if title_page is not None:
        title_blocks: list[Block] = []
        for paragraph in list(title_page):
            if local_name(paragraph.tag) != "Paragraph":
                _preserve_unknown(paragraph, losses, path="TitlePage")
                continue
            block = _block_from_paragraph(
                paragraph, losses, default_kind=BlockKind.TITLE_PAGE_ELEMENT
            )
            if block.id in seen_ids:
                continue
            title_blocks.append(block)
            seen_ids.add(block.id)
        if title_blocks:
            blocks = title_blocks + blocks
    sequences = _sequences(root, blocks, losses)
    notes = tuple(_notes(root))
    marks = tuple(_marks(root))
    tags = tuple(_tags(root))
    attachments = tuple(_attachments(root))
    document = ScreenplayDocument(
        id=doc_id,
        project_id=project_id,
        title=title,
        sequences=sequences,
        blocks=tuple(blocks),
        base_revision_id=_attr(meta, "base-revision-id") or None,
        notes=notes,
        revision_marks=marks,
        production_tags=tags,
        attachments=attachments,
        paper_size=_attr(meta, "paper-size") or "us_letter",
        style=_attr(meta, "style") or "standard_screenplay",
        schema_version=_attr(meta, "schema-version") or "1.0",
    )
    normalized = normalize(document)
    semantic_validate(normalized)
    return normalized, losses.report()


def validate_profile(root: ET.Element, losses: LossAccumulator | None = None) -> None:
    if local_name(root.tag) != "FinalDraft":
        raise FdxProfileError(f"root element must be FinalDraft, got {local_name(root.tag)}")
    if root.get("DocumentType") not in (None, DOCUMENT_TYPE):
        if losses is not None:
            losses.add("document_type", f"unexpected DocumentType {root.get('DocumentType')!r}")
        else:
            raise FdxProfileError("DocumentType must be Script")
    content = _first(root, "Content")
    if content is None:
        raise FdxProfileError("profile requires Content")
    for paragraph in root.iter():
        if local_name(paragraph.tag) != "Paragraph":
            continue
        para_type = paragraph.get("Type")
        if para_type is None:
            raise FdxProfileError("Paragraph is missing Type")
        if para_type not in ALLOWED_PARAGRAPH_TYPES:
            if losses is None:
                raise FdxProfileError(f"unsupported Paragraph Type {para_type!r}")
            losses.add(
                "unsupported_paragraph_type",
                f"Paragraph Type {para_type!r} is not in the Movie Muse profile; preserved",
                path=para_type,
            )


def _paragraph(block: Block) -> ET.Element:
    attrib = {
        "Type": KIND_TO_PARAGRAPH[block.kind],
        qname("block-id"): block.id,
        qname("schema-version"): block.schema_version,
    }
    if block.scene_id:
        attrib[qname("scene-id")] = block.scene_id
    if block.scene_number:
        attrib["Number"] = block.scene_number
        attrib[qname("scene-number")] = block.scene_number
    if block.character_cue_id:
        attrib[qname("character-cue-id")] = block.character_cue_id
    if block.dialogue_pair_id:
        attrib[qname("dialogue-pair-id")] = block.dialogue_pair_id
    if block.dual_dialogue_group_id:
        attrib[qname("dual-dialogue-group-id")] = block.dual_dialogue_group_id
    if block.is_dual_dialogue:
        attrib["DualDialogue"] = "true"
        attrib[qname("dual-dialogue")] = "true"
    for flag in BOOL_ATTRS:
        if getattr(block, flag):
            attrib[qname(flag.replace("_", "-"))] = "true"
    if block.production_tag_ids:
        attrib[qname("production-tag-ids")] = ",".join(block.production_tag_ids)
    if block.note_ids:
        attrib[qname("note-ids")] = ",".join(block.note_ids)
    if block.revision_mark_ids:
        attrib[qname("revision-mark-ids")] = ",".join(block.revision_mark_ids)
    if block.attachment_ids:
        attrib[qname("attachment-ids")] = ",".join(block.attachment_ids)
    if block.spans:
        attrib[qname("spans")] = dump_json_attr([span.to_dict() for span in block.spans])
    extras = jsonable(block.unknown_extensions)
    if not isinstance(extras, dict):
        extras = {}
    if extras.get("locked_scene"):
        attrib["Locked"] = "true"
    if extras.get("locked_page"):
        attrib["LockedPage"] = "true"
    if extras.get("omitted_scene"):
        attrib["Omitted"] = "true"
    if extras.get("ab_scene"):
        attrib["Alignment"] = str(extras["ab_scene"])
    extra_attrs = extras.get("_fdx_attributes")
    if isinstance(extra_attrs, dict):
        for key, value in extra_attrs.items():
            attrib.setdefault(str(key), str(value))
    if extras:
        attrib[qname("unknown-extensions")] = dump_json_attr(extras)
    node = elem("Paragraph", attrib=attrib)
    if block.text:
        append(node, elem("Text", text=block.text))
    return node


def _block_from_paragraph(
    paragraph: ET.Element,
    losses: LossAccumulator,
    *,
    default_kind: BlockKind | None = None,
) -> Block:
    para_type = paragraph.get("Type") or ""
    kind = PARAGRAPH_TO_KIND.get(para_type, default_kind)
    extras: dict[str, Any] = {}
    if kind is None:
        kind = BlockKind.GENERAL
        extras["_fdx_paragraph_type"] = para_type
        losses.add(
            "mapped_unknown_type",
            f"Paragraph Type {para_type!r} mapped to general and preserved",
            path=para_type,
        )
    raw_ext = paragraph.get(qname("unknown-extensions"))
    if raw_ext:
        loaded = load_json_attr(raw_ext)
        if isinstance(loaded, dict):
            extras.update(loaded)
    if paragraph.get("Locked") == "true":
        extras.setdefault("locked_scene", True)
    if paragraph.get("LockedPage") == "true":
        extras.setdefault("locked_page", True)
    if paragraph.get("Omitted") == "true":
        extras.setdefault("omitted_scene", True)
    alignment = paragraph.get("Alignment")
    if alignment in {"A", "B"}:
        extras.setdefault("ab_scene", alignment)
    consumed_local = {
        "Type",
        "Number",
        "DualDialogue",
        "Locked",
        "LockedPage",
        "Omitted",
    }
    if alignment in {"A", "B"}:
        consumed_local.add("Alignment")
    already_attrs = extras.get("_fdx_attributes")
    already_keys = set(already_attrs) if isinstance(already_attrs, dict) else set()
    for key, value in paragraph.attrib.items():
        if namespace_of(key) == MM_NS:
            continue
        local = local_name(key)
        if local in consumed_local or local in already_keys:
            continue
        extras.setdefault("_fdx_attributes", {})[local] = value
        losses.add(
            "unknown_attribute_preserved",
            f"preserved unknown Paragraph attribute {local!r}",
            severity=LossSeverity.INFO,
            path=local,
        )
    for child in list(paragraph):
        if local_name(child.tag) == "Text":
            continue
        extras.setdefault("_fdx_extra_elements", [])
        extras["_fdx_extra_elements"].append(
            {"tag": local_name(child.tag), "text": child.text, "attrib": dict(child.attrib)}
        )
        losses.add(
            "unknown_child_preserved",
            f"preserved unknown child {local_name(child.tag)!r} on Paragraph",
            severity=LossSeverity.INFO,
            path=local_name(child.tag),
        )
    text_node = next((child for child in paragraph if local_name(child.tag) == "Text"), None)
    text = (text_node.text if text_node is not None and text_node.text else "") or (paragraph.text or "")
    spans_raw = paragraph.get(qname("spans"))
    spans: tuple[InlineSpan, ...] = ()
    if spans_raw:
        loaded_spans = load_json_attr(spans_raw)
        if isinstance(loaded_spans, list):
            spans = tuple(InlineSpan.from_dict(item) for item in loaded_spans if isinstance(item, dict))
    block_id = paragraph.get(qname("block-id")) or new_id("block")
    if paragraph.get(qname("block-id")) is None:
        losses.add("minted_block_id", f"minted block id {block_id} for {para_type or kind.value}")
    scene_id = paragraph.get(qname("scene-id"))
    if kind is BlockKind.SCENE_HEADING and not scene_id:
        scene_id = new_id("scene")
        losses.add("minted_scene_id", f"minted scene id {scene_id}")
    character_cue_id = paragraph.get(qname("character-cue-id"))
    if kind is BlockKind.CHARACTER and not character_cue_id:
        character_cue_id = new_id("character_cue")
        losses.add("minted_character_cue", f"minted character cue {character_cue_id}")
    dialogue_pair_id = paragraph.get(qname("dialogue-pair-id"))
    if kind is BlockKind.DIALOGUE and not dialogue_pair_id:
        dialogue_pair_id = new_id("dialogue_pair")
        losses.add("minted_dialogue_pair", f"minted dialogue pair {dialogue_pair_id}")
    dual = paragraph.get("DualDialogue") == "true" or paragraph.get(qname("dual-dialogue")) == "true"
    dual_group = paragraph.get(qname("dual-dialogue-group-id"))
    if dual and not dual_group:
        dual_group = new_id("dialogue_pair")
        losses.add("minted_dual_group", f"minted dual dialogue group {dual_group}")
    return Block(
        id=block_id,
        kind=kind,
        text=text,
        spans=spans,
        scene_id=scene_id,
        scene_number=paragraph.get(qname("scene-number")) or paragraph.get("Number"),
        character_cue_id=character_cue_id,
        dialogue_pair_id=dialogue_pair_id,
        is_dual_dialogue=dual,
        dual_dialogue_group_id=dual_group,
        is_forced=_flag(paragraph, "is-forced"),
        is_continued=_flag(paragraph, "is-continued"),
        is_extension=_flag(paragraph, "is-extension"),
        is_boneyard=_flag(paragraph, "is-boneyard"),
        production_tag_ids=_csv(paragraph.get(qname("production-tag-ids"))),
        note_ids=_csv(paragraph.get(qname("note-ids"))),
        revision_mark_ids=_csv(paragraph.get(qname("revision-mark-ids"))),
        attachment_ids=_csv(paragraph.get(qname("attachment-ids"))),
        unknown_extensions=extras,
        schema_version=paragraph.get(qname("schema-version")) or "1.0",
    )


def _sequences(
    root: ET.Element, blocks: Iterable[Block], losses: LossAccumulator
) -> tuple[Sequence, ...]:
    container = _first(root, qname("Sequences"))
    if container is None:
        scene_ids = tuple(block.scene_id for block in blocks if block.kind is BlockKind.SCENE_HEADING and block.scene_id)
        if not scene_ids:
            return (
                Sequence(
                    id=new_id("sequence"),
                    title="Untitled",
                    order=0,
                ),
            )
        losses.add("minted_sequence", "FDX had no mm:Sequences; a sequence was reconstructed from scene headings")
        return (
            Sequence(
                id=new_id("sequence"),
                title="Untitled",
                order=0,
                scene_ids=scene_ids,
            ),
        )
    sequences: list[Sequence] = []
    for child in list(container):
        if local_name(child.tag) != "Sequence":
            continue
        scene_ids = tuple(
            ref.get("id") or ""
            for ref in child
            if local_name(ref.tag) == "SceneRef" and ref.get("id")
        )
        sequences.append(
            Sequence(
                id=child.get("id") or new_id("sequence"),
                title=child.get("title") or "Untitled",
                order=int(child.get("order") or 0),
                scene_ids=scene_ids,
                schema_version=child.get("schema-version") or "1.0",
            )
        )
    return tuple(sequences)


def _notes(root: ET.Element) -> list[Note]:
    container = _first(root, qname("Notes"))
    if container is None:
        return []
    notes: list[Note] = []
    for child in list(container):
        if local_name(child.tag) != "Note":
            continue
        notes.append(
            Note(
                id=child.get("id") or new_id("note"),
                block_id=child.get("block-id") or "",
                author_actor_id=child.get("author-actor-id") or "act_unknown",
                text=child.text or "",
                created_at=child.get("created-at") or "2026-09-01T00:00:00Z",
                resolved=child.get("resolved") == "true",
                schema_version=child.get("schema-version") or "1.0",
            )
        )
    return notes


def _marks(root: ET.Element) -> list[RevisionMark]:
    container = _first(root, qname("RevisionMarks"))
    if container is None:
        return []
    marks: list[RevisionMark] = []
    for child in list(container):
        if local_name(child.tag) != "RevisionMark":
            continue
        marks.append(
            RevisionMark(
                id=child.get("id") or new_id("revision_mark"),
                block_id=child.get("block-id") or "",
                revision_color=child.get("revision-color") or "blue",
                revision_label=child.get("revision-label") or "1",
                created_at=child.get("created-at") or "2026-09-01T00:00:00Z",
                schema_version=child.get("schema-version") or "1.0",
            )
        )
    return marks


def _tags(root: ET.Element) -> list[ProductionTag]:
    container = _first(root, qname("ProductionTags"))
    if container is None:
        return []
    tags: list[ProductionTag] = []
    for child in list(container):
        if local_name(child.tag) != "ProductionTag":
            continue
        tags.append(
            ProductionTag(
                id=child.get("id") or new_id("production_tag"),
                block_id=child.get("block-id") or "",
                department=child.get("department") or "unspecified",
                tag_type=child.get("tag-type") or "tag",
                value=child.get("value") or "",
                schema_version=child.get("schema-version") or "1.0",
            )
        )
    return tags


def _attachments(root: ET.Element) -> list[Attachment]:
    container = _first(root, qname("Attachments"))
    if container is None:
        return []
    attachments: list[Attachment] = []
    for child in list(container):
        if local_name(child.tag) != "Attachment":
            continue
        attachments.append(
            Attachment(
                id=child.get("id") or new_id("attachment"),
                kind=child.get("kind") or "file",
                uri=child.get("uri") or "",
                checksum=child.get("checksum") or "",
                block_id=child.get("block-id") or None,
                schema_version=child.get("schema-version") or "1.0",
            )
        )
    return attachments


def _preserve_unknown(node: ET.Element, losses: LossAccumulator, *, path: str) -> None:
    losses.add(
        "unknown_element_disclosed",
        f"unknown element {local_name(node.tag)!r} under {path} was not mapped into typed blocks",
        path=f"{path}/{local_name(node.tag)}",
    )


def _first(root: ET.Element, tag: str) -> ET.Element | None:
    wanted_local = local_name(tag)
    wanted_ns = namespace_of(tag)
    for child in list(root):
        if local_name(child.tag) != wanted_local:
            continue
        if wanted_ns is None or namespace_of(child.tag) in {wanted_ns, None}:
            return child
        if wanted_ns == MM_NS and namespace_of(child.tag) == MM_NS:
            return child
    # ElementTree may keep mm tags as {ns}Local
    for child in list(root):
        if child.tag == tag:
            return child
    return None


def _attr(node: ET.Element | None, name: str) -> str | None:
    if node is None:
        return None
    value = node.get(name) or node.get(qname(name))
    return value or None


def _flag(paragraph: ET.Element, local: str) -> bool:
    return paragraph.get(qname(local)) == "true"


def _csv(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(part for part in raw.split(",") if part)
