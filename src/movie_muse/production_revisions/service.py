"""Changed-page detection, A/B labels, omitted occupancy, sides, clean/revision export."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from movie_muse.authorization.api import Action, AuthorizationError
from movie_muse.identity.api import Principal
from movie_muse.layout.api import (
    LayoutResult,
    LayoutService,
    ProductionLockState,
    lock_state_from_document,
)
from movie_muse.production_revisions.errors import SidesError, UnlockDeniedError
from movie_muse.production_revisions.events import make_unlock_event
from movie_muse.schemas.api import BlockKind, ProjectEvent, ScreenplayDocument, new_id


@dataclass(frozen=True, slots=True)
class ChangedPages:
    previous_hash: str
    current_hash: str
    page_labels: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "previous_hash": self.previous_hash,
            "current_hash": self.current_hash,
            "page_labels": list(self.page_labels),
        }


@dataclass(frozen=True, slots=True)
class SidesPacket:
    id: str
    scene_ids: tuple[str, ...]
    layout: LayoutResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scene_ids": list(self.scene_ids),
            "layout_hash": self.layout.layout_hash,
            "pages": len(self.layout.pages),
        }


class ProductionRevisionService:
    """Overlays on LayoutResult. Does not rewrite ScreenplayDocument canon."""

    def __init__(self, layout: LayoutService | None = None) -> None:
        self.layout = layout or LayoutService()

    def changed_pages(self, previous: LayoutResult, current: LayoutResult) -> ChangedPages:
        prev = {page.label: _page_fingerprint(page) for page in previous.script_pages()}
        curr = {page.label: _page_fingerprint(page) for page in current.script_pages()}
        labels = tuple(
            sorted(label for label in set(prev) | set(curr) if prev.get(label) != curr.get(label))
        )
        return ChangedPages(
            previous_hash=previous.layout_hash,
            current_hash=current.layout_hash,
            page_labels=labels,
        )

    def ab_scene_labels(self, document: ScreenplayDocument) -> tuple[str, ...]:
        labels: list[str] = []
        for block in document.blocks:
            extras = dict(block.unknown_extensions)
            suffix = extras.get("ab_scene")
            if suffix in {"A", "B"} and block.kind is BlockKind.SCENE_HEADING:
                number = block.scene_number or ""
                if number.endswith(str(suffix)):
                    labels.append(number)
                else:
                    labels.append(f"{number}{suffix}")
        return tuple(labels)

    def omitted_scene_ids(self, document: ScreenplayDocument) -> tuple[str, ...]:
        return tuple(
            block.scene_id
            for block in document.blocks
            if block.kind is BlockKind.SCENE_HEADING
            and block.scene_id
            and dict(block.unknown_extensions).get("omitted_scene")
        )

    def sides(
        self,
        document: ScreenplayDocument,
        scene_ids: tuple[str, ...],
        *,
        production_lock_state: ProductionLockState | None = None,
    ) -> SidesPacket:
        wanted = set(scene_ids)
        if not wanted:
            raise SidesError("sides require at least one scene id")
        selected = tuple(
            block
            for block in document.blocks
            if block.kind is BlockKind.TITLE_PAGE_ELEMENT or block.scene_id in wanted
        )
        if not any(block.scene_id in wanted for block in selected):
            raise SidesError("none of the requested scenes exist on the document")
        present_scenes = {block.scene_id for block in selected if block.scene_id}
        sequences = tuple(
            replace(
                sequence,
                scene_ids=tuple(scene_id for scene_id in sequence.scene_ids if scene_id in present_scenes),
            )
            for sequence in document.sequences
            if any(scene_id in present_scenes for scene_id in sequence.scene_ids)
        )
        sides_doc = replace(
            document,
            title=f"{document.title} — SIDES",
            sequences=sequences,
            blocks=selected,
            notes=tuple(note for note in document.notes if any(block.id == note.block_id for block in selected)),
            revision_marks=tuple(
                mark for mark in document.revision_marks if any(block.id == mark.block_id for block in selected)
            ),
            production_tags=tuple(
                tag for tag in document.production_tags if any(block.id == tag.block_id for block in selected)
            ),
        )
        lock_state = production_lock_state
        if lock_state is None:
            lock_state = lock_state_from_document(sides_doc)
        return SidesPacket(
            id=new_id("artifact"),
            scene_ids=scene_ids,
            layout=self.layout.layout(sides_doc, production_lock_state=lock_state),
        )

    def clean_export(self, result: LayoutResult) -> tuple[str, ...]:
        return tuple(
            line.text
            for line in result.lines
            if line.line_kind not in {"header", "footer", "blank"} and line.text
        )

    def revision_export(self, result: LayoutResult, document: ScreenplayDocument) -> tuple[str, ...]:
        marked = {mark.block_id: mark.revision_color for mark in document.revision_marks}
        lines: list[str] = []
        for line in result.lines:
            if line.line_kind in {"header", "footer", "blank"} or not line.text:
                continue
            color = line.revision_color or marked.get(line.block_id or "")
            if color:
                lines.append(f"{line.text} [*{color}*]")
            else:
                lines.append(line.text)
        return tuple(lines)

    def unlock_repagination(
        self,
        *,
        authorization: Any,
        principal: Principal,
        resource: Any,
        acl_epoch: int,
        project_id: str,
        branch_id: str,
        result_revision_id: str,
        base_revision_id: str | None = None,
    ) -> ProjectEvent:
        if authorization is None:
            raise UnlockDeniedError("unlocking requires an authorization service")
        require = getattr(authorization, "require", None)
        if require is None:
            raise UnlockDeniedError("authorization service cannot evaluate manage_production_locks")
        try:
            require(
                principal,
                Action.MANAGE_PRODUCTION_LOCKS,
                resource,
                acl_epoch=acl_epoch,
            )
        except AuthorizationError as exc:
            raise UnlockDeniedError("unlocking denied without manage_production_locks") from exc
        return make_unlock_event(
            project_id=project_id,
            branch_id=branch_id,
            result_revision_id=result_revision_id,
            actor_id=principal.actor_id,
            base_revision_id=base_revision_id,
        )

    def layout_unlocked(
        self,
        document: ScreenplayDocument,
        *,
        authorization: Any,
        principal: Principal,
        resource: Any,
        acl_epoch: int,
        project_id: str,
        branch_id: str,
        result_revision_id: str,
        base_revision_id: str | None = None,
    ) -> tuple[LayoutResult, ProjectEvent]:
        event = self.unlock_repagination(
            authorization=authorization,
            principal=principal,
            resource=resource,
            acl_epoch=acl_epoch,
            project_id=project_id,
            branch_id=branch_id,
            result_revision_id=result_revision_id,
            base_revision_id=base_revision_id,
        )
        result = self.layout.layout(document, production_lock_state=ProductionLockState.unlocked())
        return result, event

    def record_unlock(self, **kwargs: Any) -> ProjectEvent:
        return make_unlock_event(**kwargs)


def _page_fingerprint(page: Any) -> tuple[Any, ...]:
    return (
        page.page_number,
        page.locked,
        tuple((line.block_id, line.line_kind, line.text, line.x_chars) for line in page.lines),
    )


__all__ = ["ChangedPages", "ProductionRevisionService", "SidesPacket"]
