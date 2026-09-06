"""Deterministic history/diff projections and inspectable UTF-8/HTML renders."""

from __future__ import annotations

import hashlib
import html
from dataclasses import replace

from movie_muse.revisions.types import HistoryProjection, HistoryRecord
from movie_muse.schemas.api import ChangeSet


def render_history_text(projection: HistoryProjection) -> str:
    lines = [
        f"HISTORY branch={projection.branch_id} name={projection.branch_name}",
        f"HEAD {projection.head_revision_id}",
        f"RECORDS {len(projection.records)}",
    ]
    for index, record in enumerate(projection.records):
        lines.append(_record_line(index, record))
    return "\n".join(lines) + "\n"


def render_history_html(projection: HistoryProjection) -> str:
    items: list[str] = []
    for index, record in enumerate(projection.records):
        checkpoints = html.escape(",".join(record.checkpoint_names) or "-")
        branches = html.escape(",".join(record.branch_names) or "-")
        events = html.escape(",".join(record.event_ids) or "-")
        parent = html.escape(record.parent_revision_id or "-")
        items.append(
            "<li data-index=\"{index}\" data-revision-id=\"{rev}\">"
            "<time datetime=\"{ts}\">{ts}</time> "
            "revision {rev} parent {parent} actor {actor} "
            "events {events} checkpoints {cps} branches {bns}"
            "</li>".format(
                index=index,
                rev=html.escape(record.revision_id),
                ts=html.escape(record.timestamp),
                parent=parent,
                actor=html.escape(record.actor_id),
                events=events,
                cps=checkpoints,
                bns=branches,
            )
        )
    body = "\n".join(items)
    return (
        "<article data-history-projection=\"1\">"
        f"<h1>History of {html.escape(projection.branch_name)}</h1>"
        f"<p>Branch {html.escape(projection.branch_id)} head "
        f"{html.escape(projection.head_revision_id)}</p>"
        f"<ol>{body}</ol>"
        "</article>\n"
    )


def render_diff_text(change_set: ChangeSet) -> str:
    lines = [
        f"DIFF base={change_set.base_revision_id} author={change_set.author_actor_id}",
        f"CREATED {change_set.created_at}",
        f"OPERATIONS {len(change_set.operations)}",
    ]
    for operation in change_set.operations:
        lines.append(f"{operation.order:04d} {operation.op_type.value} {operation.target_id}")
    return "\n".join(lines) + "\n"


def stabilize_diff_change_set(
    change_set: ChangeSet,
    *,
    from_revision_id: str,
    to_revision_id: str,
    created_at: str,
) -> ChangeSet:
    """Replace wall-clock ChangeSet identity with one derived from the revision pair.

    ``structural_diff`` mints a new ULID and callers used to pass ``utc_now()``.
    A projection of two immutable revisions must not change when called later.
    """

    material = "\0".join(
        (from_revision_id, to_revision_id, change_set.author_actor_id, created_at)
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return replace(change_set, id=f"cst_{digest[:26]}", created_at=created_at)


def _record_line(index: int, record: HistoryRecord) -> str:
    checkpoints = ",".join(record.checkpoint_names) or "-"
    branches = ",".join(record.branch_names) or "-"
    events = ",".join(record.event_ids) or "-"
    parent = record.parent_revision_id or "-"
    return (
        f"{index:04d} rev={record.revision_id} parent={parent} "
        f"actor={record.actor_id} at={record.timestamp} "
        f"events={events} checkpoints={checkpoints} branches={branches}"
    )
