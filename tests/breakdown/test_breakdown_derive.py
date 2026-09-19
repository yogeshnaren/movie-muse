"""Locked-revision derivation, evidence links, and completeness thresholds."""

from __future__ import annotations

import pytest

from movie_muse.authorization.api import AuthorizationError
from movie_muse.breakdown.api import (
    DECLARED_THRESHOLDS,
    ElementKind,
    UnlockedSourceError,
    UnverifiedEditError,
    VerificationState,
)
from movie_muse.identity.api import Role, make_human_actor
from movie_muse.schemas.api import FilmIR, FilmIrEntity, FilmIrEntityKind, new_id


def _lock_and_derive(stack, film_ir=None):
    stack.breakdown.lock_source_revision(
        project_id=stack.project.id,
        revision_id=stack.head,
        principal=stack.principal,
        acl_epoch=stack.epoch,
    )
    return stack.breakdown.derive(
        project_id=stack.project.id,
        revision_id=stack.head,
        principal=stack.principal,
        acl_epoch=stack.epoch,
        film_ir=film_ir,
    )


def test_unlocked_source_fails_closed(breakdown_stack) -> None:
    with pytest.raises(UnlockedSourceError):
        breakdown_stack.breakdown.derive(
            project_id=breakdown_stack.project.id,
            revision_id=breakdown_stack.head,
            principal=breakdown_stack.principal,
            acl_epoch=breakdown_stack.epoch,
        )


def test_derive_links_cast_location_prop_timing_and_cues(breakdown_stack) -> None:
    stored = _lock_and_derive(breakdown_stack)
    kinds = {item.kind for item in stored.elements}
    names = {(item.kind, item.name.casefold()) for item in stored.elements}
    assert ElementKind.CAST in kinds
    assert ElementKind.LOCATION in kinds
    assert ElementKind.PROP in kinds
    assert ElementKind.TIMING in kinds
    assert ElementKind.EXTRAS in kinds
    assert ElementKind.VEHICLE in kinds
    assert ElementKind.SOUND in kinds
    assert ElementKind.WARDROBE in kinds
    assert ElementKind.MINOR in kinds
    assert ElementKind.SAFETY in kinds
    assert (ElementKind.CAST, "ada") in names
    assert (ElementKind.PROP, "brass key") in names
    assert ElementKind.ANIMAL not in kinds
    assert ElementKind.VFX not in kinds
    block_ids = {block.id for block in breakdown_stack.document.blocks}
    for element in stored.elements:
        assert element.verification is VerificationState.DERIVED
        assert element.evidence
        assert all(item.block_id in block_ids for item in element.evidence)
        assert all(item.excerpt for item in element.evidence)
    assert stored.projection.id.startswith("opj_")
    assert all(item.id.startswith("bke_") for item in stored.elements)


def test_film_ir_prop_merges_into_breakdown(breakdown_stack) -> None:
    mention = breakdown_stack.document.blocks[1].id
    film_ir = FilmIR(
        id=new_id("film_ir"),
        project_id=breakdown_stack.project.id,
        source_revision_id=breakdown_stack.head,
        extractor_version="1.0.0",
        computed_at="2026-09-01T00:00:00Z",
        entities=(
            FilmIrEntity(
                id=new_id("structural_fact"),
                kind=FilmIrEntityKind.PROP,
                canonical_name="LETTER",
                scene_ids=(breakdown_stack.scene_ids[0],),
                mention_block_ids=(mention,),
            ),
        ),
    )
    stored = _lock_and_derive(breakdown_stack, film_ir=film_ir)
    props = {item.name.casefold() for item in stored.elements if item.kind is ElementKind.PROP}
    assert "letter" in props
    assert "brass key" in props


def test_completeness_thresholds_require_human_verification(breakdown_stack) -> None:
    stored = _lock_and_derive(breakdown_stack)
    report = breakdown_stack.breakdown.completeness_report(
        stored.projection.id,
        principal=breakdown_stack.principal,
        acl_epoch=breakdown_stack.epoch,
    )
    assert report.completeness < DECLARED_THRESHOLDS["completeness"]
    assert report.accuracy >= DECLARED_THRESHOLDS["accuracy"]
    assert report.evidence_link_rate >= DECLARED_THRESHOLDS["evidence_link_rate"]
    assert report.meets_thresholds is False
    assert report.current is True
    with pytest.raises(UnverifiedEditError):
        breakdown_stack.breakdown.require_complete(
            stored.projection.id,
            principal=breakdown_stack.principal,
            acl_epoch=breakdown_stack.epoch,
        )
    current = stored
    for element in stored.elements:
        current = breakdown_stack.breakdown.verify_element(
            current.projection.id,
            element.id,
            principal=breakdown_stack.principal,
            acl_epoch=breakdown_stack.epoch,
        )
    complete = breakdown_stack.breakdown.require_complete(
        current.projection.id,
        principal=breakdown_stack.principal,
        acl_epoch=breakdown_stack.epoch,
    )
    assert complete.completeness >= DECLARED_THRESHOLDS["completeness"]
    assert complete.accuracy >= DECLARED_THRESHOLDS["accuracy"]
    assert complete.evidence_link_rate >= DECLARED_THRESHOLDS["evidence_link_rate"]
    assert complete.meets_thresholds is True
    assert complete.derived_count == 0
    assert complete.verified_count == len(current.elements)


def test_viewer_cannot_lock_or_derive(breakdown_stack) -> None:
    actor = make_human_actor(
        organization_id=breakdown_stack.project.organization_id, display_name="Viewer"
    )
    breakdown_stack.identity.register_actor(actor)
    invitation = breakdown_stack.identity.invite(
        inviter_actor_id=breakdown_stack.owner.id,
        invitee_actor_id=actor.id,
        project_id=breakdown_stack.project.id,
        role=Role.VIEWER,
    )
    breakdown_stack.identity.accept_invitation(invitation.id, actor_id=actor.id)
    viewer = breakdown_stack.identity.principal(actor.id)
    epoch = breakdown_stack.identity.acl_epoch()
    with pytest.raises(AuthorizationError):
        breakdown_stack.breakdown.lock_source_revision(
            project_id=breakdown_stack.project.id,
            revision_id=breakdown_stack.head,
            principal=viewer,
            acl_epoch=epoch,
        )
    stored = _lock_and_derive(breakdown_stack)
    readable = breakdown_stack.breakdown.get_breakdown(
        stored.projection.id, principal=viewer, acl_epoch=epoch
    )
    assert readable.projection.id == stored.projection.id
    with pytest.raises(AuthorizationError):
        breakdown_stack.breakdown.verify_element(
            stored.projection.id,
            stored.elements[0].id,
            principal=viewer,
            acl_epoch=epoch,
        )
