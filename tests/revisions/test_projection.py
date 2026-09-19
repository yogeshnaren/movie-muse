"""Stable history/diff projection renders for a fixture history."""

from __future__ import annotations

from movie_muse.revisions.api import (
    HistoryProjection,
    HistoryRecord,
    render_diff_text,
    render_history_html,
    render_history_text,
)
from movie_muse.schemas.api import ChangeSet, ChangeSetOperation, OperationType, new_id

FIXTURE_HISTORY = HistoryProjection(
    branch_id="brn_fixturemain00000000000001",
    branch_name="main",
    head_revision_id="rev_fixturehead00000000000001",
    records=(
        HistoryRecord(
            revision_id="rev_fixturebase00000000000001",
            parent_revision_id=None,
            actor_id="act_fixtureauthor000000000001",
            timestamp="2026-09-01T00:00:00Z",
            event_ids=("evt_fixtureboot00000000000001",),
            checkpoint_names=(),
            branch_names=(),
        ),
        HistoryRecord(
            revision_id="rev_fixturehead00000000000001",
            parent_revision_id="rev_fixturebase00000000000001",
            actor_id="act_fixtureauthor000000000001",
            timestamp="2026-09-01T00:01:00Z",
            event_ids=("evt_fixturepatch0000000000001",),
            checkpoint_names=("blue-pages",),
            branch_names=("main",),
        ),
    ),
)

EXPECTED_HISTORY_TEXT = """\
HISTORY branch=brn_fixturemain00000000000001 name=main
HEAD rev_fixturehead00000000000001
RECORDS 2
0000 rev=rev_fixturebase00000000000001 parent=- actor=act_fixtureauthor000000000001 at=2026-09-01T00:00:00Z events=evt_fixtureboot00000000000001 checkpoints=- branches=-
0001 rev=rev_fixturehead00000000000001 parent=rev_fixturebase00000000000001 actor=act_fixtureauthor000000000001 at=2026-09-01T00:01:00Z events=evt_fixturepatch0000000000001 checkpoints=blue-pages branches=main
"""

EXPECTED_HISTORY_HTML = (
    '<article data-history-projection="1">'
    "<h1>History of main</h1>"
    "<p>Branch brn_fixturemain00000000000001 head rev_fixturehead00000000000001</p>"
    "<ol>"
    '<li data-index="0" data-revision-id="rev_fixturebase00000000000001">'
    '<time datetime="2026-09-01T00:00:00Z">2026-09-01T00:00:00Z</time> '
    "revision rev_fixturebase00000000000001 parent - actor act_fixtureauthor000000000001 "
    "events evt_fixtureboot00000000000001 checkpoints - branches -</li>\n"
    '<li data-index="1" data-revision-id="rev_fixturehead00000000000001">'
    '<time datetime="2026-09-01T00:01:00Z">2026-09-01T00:01:00Z</time> '
    "revision rev_fixturehead00000000000001 parent rev_fixturebase00000000000001 "
    "actor act_fixtureauthor000000000001 "
    "events evt_fixturepatch0000000000001 checkpoints blue-pages branches main</li>"
    "</ol>"
    "</article>\n"
)


def test_history_text_render_matches_fixture_exactly() -> None:
    assert render_history_text(FIXTURE_HISTORY) == EXPECTED_HISTORY_TEXT
    assert render_history_text(FIXTURE_HISTORY) == render_history_text(FIXTURE_HISTORY)


def test_history_html_render_matches_fixture_exactly() -> None:
    assert render_history_html(FIXTURE_HISTORY) == EXPECTED_HISTORY_HTML


def test_history_html_escapes_checkpoint_names() -> None:
    projection = HistoryProjection(
        branch_id="brn_x",
        branch_name="<main>",
        head_revision_id="rev_x",
        records=(
            HistoryRecord(
                revision_id="rev_x",
                parent_revision_id=None,
                actor_id="act_x",
                timestamp="2026-09-01T00:00:00Z",
                checkpoint_names=('<script>alert("x")</script>',),
            ),
        ),
    )
    rendered = render_history_html(projection)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "&lt;main&gt;" in rendered


def test_diff_text_render_is_stable_for_fixture_changeset() -> None:
    change_set = ChangeSet(
        id=new_id("change_set"),
        base_revision_id="rev_base",
        author_actor_id="act_author",
        created_at="2026-09-01T00:00:00Z",
        operations=(
            ChangeSetOperation(
                id="op-0",
                order=0,
                op_type=OperationType.UPDATE_BLOCK,
                target_id="blk_action",
                payload={"text": "Ada picks the lock."},
            ),
        ),
    )
    expected = (
        "DIFF base=rev_base author=act_author\n"
        "CREATED 2026-09-01T00:00:00Z\n"
        "OPERATIONS 1\n"
        "0000 update_block blk_action\n"
    )
    assert render_diff_text(change_set) == expected
    assert render_diff_text(change_set) == render_diff_text(change_set)
