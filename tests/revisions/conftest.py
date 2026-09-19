"""Builders for revisions tests. Duplicated here rather than imported from other test packages."""

from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
from movie_muse.schemas.api import (
    Block,
    BlockKind,
    ChangeSet,
    ChangeSetOperation,
    Note,
    OperationType,
    ProductionTag,
    Project,
    Proposal,
    ProposalStatus,
    RevisionMark,
    ScreenplayDocument,
    Sequence,
    new_id,
)


def make_project_and_document() -> tuple[Project, ScreenplayDocument, str]:
    actor_id = new_id("actor")
    project = Project(
        id=new_id("project"),
        organization_id="org_local",
        title="Pilot",
        owner_actor_id=actor_id,
        created_at="2026-09-01T00:00:00Z",
    )
    scene_id = new_id("scene")
    cue_id = new_id("character_cue")
    pair_id = new_id("dialogue_pair")
    heading = Block(
        id=new_id("block"),
        kind=BlockKind.SCENE_HEADING,
        text="INT. KITCHEN - DAY",
        scene_id=scene_id,
        scene_number="1",
    )
    action = Block(id=new_id("block"), kind=BlockKind.ACTION, text="Ada studies the lock.")
    character = Block(
        id=new_id("block"),
        kind=BlockKind.CHARACTER,
        text="ADA",
        character_cue_id=cue_id,
        dialogue_pair_id=pair_id,
    )
    dialogue = Block(
        id=new_id("block"),
        kind=BlockKind.DIALOGUE,
        text="It's not locked.",
        dialogue_pair_id=pair_id,
    )
    document = ScreenplayDocument(
        id=new_id("document"),
        project_id=project.id,
        title="Pilot",
        sequences=(Sequence(id=new_id("sequence"), title="Act One", order=0, scene_ids=(scene_id,)),),
        blocks=(heading, action, character, dialogue),
        notes=(
            Note(
                id=new_id("note"),
                block_id=heading.id,
                author_actor_id=actor_id,
                text="confirm kitchen",
                created_at="2026-09-01T00:00:00Z",
            ),
        ),
        production_tags=(
            ProductionTag(
                id=new_id("production_tag"),
                block_id=heading.id,
                department="props",
                tag_type="required_prop",
                value="lockpick set",
            ),
        ),
        revision_marks=(
            RevisionMark(
                id=new_id("revision_mark"),
                block_id=action.id,
                revision_color="blue",
                revision_label="2nd Blue",
                created_at="2026-09-01T00:00:00Z",
            ),
        ),
        base_revision_id=new_id("revision"),
    )
    document.validate()
    return project, document, new_id("branch")


def update_block_change_set(
    *,
    base_revision_id: str,
    actor_id: str,
    block_id: str,
    text: str,
    created_at: str = "2026-09-01T00:00:00Z",
) -> ChangeSet:
    return ChangeSet(
        id=new_id("change_set"),
        base_revision_id=base_revision_id,
        author_actor_id=actor_id,
        created_at=created_at,
        operations=(
            ChangeSetOperation(
                id="op-0",
                order=0,
                op_type=OperationType.UPDATE_BLOCK,
                target_id=block_id,
                payload={"text": text},
            ),
        ),
    )


def make_proposal(
    *,
    project_id: str,
    change_set: ChangeSet,
    intent: str = "tighten action",
) -> Proposal:
    return Proposal(
        id=new_id("proposal"),
        project_id=project_id,
        change_set=change_set,
        base_revision_id=change_set.base_revision_id,
        intent=intent,
        rationale_summary="candidate patch",
        provenance="human-author",
        created_at="2026-09-01T00:00:00Z",
        status=ProposalStatus.PENDING,
    )


@pytest.fixture
def project_bundle() -> tuple[Project, ScreenplayDocument, str]:
    return make_project_and_document()


@pytest.fixture
def bound_service(
    tmp_path: Path, project_bundle: tuple[Project, ScreenplayDocument, str]
) -> tuple[RevisionService, Project, ScreenplayDocument, str]:
    project, document, branch_id = project_bundle
    workspace = LocalWorkspace(tmp_path / "ws")
    workspace.open_project(project, document, branch_id=branch_id)
    service = RevisionService(workspace)
    service.bind(actor_id=project.owner_actor_id)
    return service, project, document, branch_id
