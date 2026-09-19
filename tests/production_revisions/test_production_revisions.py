"""Changed pages, A/B scenes, omitted occupancy, sides, exports, unlock events."""

from __future__ import annotations

from dataclasses import replace

import pytest

from movie_muse.authorization.api import Action, AuthorizationError, Resource, ResourceKind
from movie_muse.identity.api import Principal, PrincipalKind
from movie_muse.layout.api import LayoutService, ProductionLockState
from movie_muse.production_revisions.api import (
    EVENT_TYPE,
    ProductionRevisionService,
    SidesError,
    UnlockDeniedError,
)
from movie_muse.schemas.api import new_id
from movie_muse.testkit.api import FixtureCatalog


class _DenyAuth:
    def require(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise AuthorizationError("denied")


class _AllowAuth:
    def require(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


def _principal() -> Principal:
    return Principal(
        actor_id="act_01J6NE39000000000000000001",
        kind=PrincipalKind.HUMAN,
        organization_id="org_01J6NE39000000000000000001",
        display_name="Ada",
    )


def _resource() -> Resource:
    return Resource(
        kind=ResourceKind.PROJECT,
        id="proj_01J6NE39000000000000000001",
        organization_id="org_01J6NE39000000000000000001",
        project_id="proj_01J6NE39000000000000000001",
    )


def test_changed_pages_and_exports() -> None:
    catalog = FixtureCatalog()
    kitchen = catalog.get("small_kitchen").document
    production = catalog.get("production_locked_sides").document
    layout = LayoutService()
    revisions = ProductionRevisionService(layout)
    first = layout.layout(kitchen)
    second = layout.layout(production)
    changed = revisions.changed_pages(first, second)
    assert changed.page_labels
    assert changed.previous_hash != changed.current_hash
    clean = revisions.clean_export(layout.layout(production))
    marked = revisions.revision_export(layout.layout(production), production)
    assert any("[*blue*]" in line for line in marked)
    assert not any("[*" in line for line in clean)


def test_ab_omitted_and_sides() -> None:
    document = FixtureCatalog().get("production_locked_sides").document
    revisions = ProductionRevisionService()
    assert "12A" in revisions.ab_scene_labels(document)
    assert "12B" in revisions.ab_scene_labels(document)
    omitted = revisions.omitted_scene_ids(document)
    assert omitted
    holdover = next(
        block.scene_id
        for block in document.blocks
        if block.unknown_extensions.get("ab_scene") == "B" and block.scene_id
    )
    packet = revisions.sides(document, (holdover,))
    assert packet.id.startswith("art_")
    assert packet.scene_ids == (holdover,)
    assert packet.layout.pages
    texts = "\n".join(line.text for line in packet.layout.lines)
    assert "12B" in texts or "holdover" in texts.lower()
    with pytest.raises(SidesError):
        revisions.sides(document, ())
    with pytest.raises(SidesError):
        revisions.sides(document, ("scn_missing",))


def test_unlock_requires_manage_production_locks() -> None:
    document = FixtureCatalog().get("production_locked_sides").document
    revisions = ProductionRevisionService()
    kwargs = {
        "principal": _principal(),
        "resource": _resource(),
        "acl_epoch": 1,
        "project_id": document.project_id,
        "branch_id": new_id("branch"),
        "result_revision_id": new_id("revision"),
    }
    with pytest.raises(UnlockDeniedError):
        revisions.unlock_repagination(authorization=None, **kwargs)
    with pytest.raises(UnlockDeniedError):
        revisions.unlock_repagination(authorization=_DenyAuth(), **kwargs)
    event = revisions.unlock_repagination(authorization=_AllowAuth(), **kwargs)
    assert event.event_type == EVENT_TYPE
    assert event.payload["requirement"] == "unlock_repagination"
    unlocked, recorded = revisions.layout_unlocked(document, authorization=_AllowAuth(), **kwargs)
    assert recorded.event_type == EVENT_TYPE
    locked_block = next(
        block.id for block in document.blocks if block.unknown_extensions.get("locked_page")
    )
    page = next(line.page_number for line in unlocked.lines if line.block_id == locked_block)
    assert not page.startswith("10")
    assert Action.MANAGE_PRODUCTION_LOCKS.value == "manage_production_locks"
    assert ProductionLockState.unlocked().pages_locked is False
    # replace() keeps canon typed; sides must not mutate the source document
    assert replace(document, title=document.title).blocks == document.blocks
