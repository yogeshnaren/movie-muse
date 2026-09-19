"""Stable golden project shared by every platform host."""

from __future__ import annotations

from movie_muse.schemas.api import (
    Block,
    BlockKind,
    Note,
    Project,
    ScreenplayDocument,
    Sequence,
)

GOLDEN_ACTOR_ID = "act_01H9N49B00040G2081040G2081"
GOLDEN_PROJECT_ID = "proj_01H9N49B01081040G2081040G2"
GOLDEN_DOCUMENT_ID = "doc_01H9N49B020C1G60R30C1G60R3"
GOLDEN_REVISION_ID = "rev_01H9N49B030G2081040G208104"
GOLDEN_BRANCH_ID = "brn_01H9N49B040M2GA1850M2GA185"
GOLDEN_SCENE_ID = "scn_01H9N49B050R30C1G60R30C1G6"
GOLDEN_HEADING_ID = "blk_01H9N49B060W3GE1R70W3GE1R7"
GOLDEN_SEQUENCE_ID = "seq_01H9N49B071040G2081040G208"
GOLDEN_NOTE_ID = "note_01H9N49B08144GJ289144GJ289"
GOLDEN_ACTION_ID = "blk_01H9N49B0A1850M2GA1850M2GA"
GOLDEN_CHARACTER_ID = "blk_01H9N49B0B1C5GP2RB1C5GP2RB"
GOLDEN_DIALOGUE_ID = "blk_01H9N49B0C1G60R30C1G60R30C"
GOLDEN_CUE_ID = "cue_01H9N49B0D1M6GT38D1M6GT38D"
GOLDEN_PAIR_ID = "dlg_01H9N49B0E1R70W3GE1R70W3GE"
GOLDEN_ORGANIZATION_ID = "org_local"
GOLDEN_TITLE = "Golden Path"


def golden_project_and_document() -> tuple[Project, ScreenplayDocument, str]:
    """Return the same project, document, and branch on every platform."""

    project = Project(
        id=GOLDEN_PROJECT_ID,
        organization_id=GOLDEN_ORGANIZATION_ID,
        title=GOLDEN_TITLE,
        owner_actor_id=GOLDEN_ACTOR_ID,
        created_at="2026-09-01T00:00:00Z",
    )
    document = ScreenplayDocument(
        id=GOLDEN_DOCUMENT_ID,
        project_id=GOLDEN_PROJECT_ID,
        title=GOLDEN_TITLE,
        sequences=(
            Sequence(
                id=GOLDEN_SEQUENCE_ID,
                title="Act One",
                order=0,
                scene_ids=(GOLDEN_SCENE_ID,),
            ),
        ),
        blocks=(
            Block(
                id=GOLDEN_HEADING_ID,
                kind=BlockKind.SCENE_HEADING,
                text="INT. STAGE - DAY",
                scene_id=GOLDEN_SCENE_ID,
                scene_number="1",
            ),
            Block(
                id=GOLDEN_ACTION_ID,
                kind=BlockKind.ACTION,
                text="Ada checks the call sheet.",
                scene_id=GOLDEN_SCENE_ID,
            ),
            Block(
                id=GOLDEN_CHARACTER_ID,
                kind=BlockKind.CHARACTER,
                text="ADA",
                character_cue_id=GOLDEN_CUE_ID,
                dialogue_pair_id=GOLDEN_PAIR_ID,
            ),
            Block(
                id=GOLDEN_DIALOGUE_ID,
                kind=BlockKind.DIALOGUE,
                text="Hold for playback.",
                dialogue_pair_id=GOLDEN_PAIR_ID,
            ),
        ),
        notes=(
            Note(
                id=GOLDEN_NOTE_ID,
                block_id=GOLDEN_HEADING_ID,
                author_actor_id=GOLDEN_ACTOR_ID,
                text="onset reference: call sheet",
                created_at="2026-09-01T00:00:00Z",
            ),
        ),
        base_revision_id=GOLDEN_REVISION_ID,
    )
    document.validate()
    return project, document, GOLDEN_BRANCH_ID
