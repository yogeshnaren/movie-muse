"""Keyboard and accessibility contracts for the authoring surface."""

from __future__ import annotations

from pathlib import Path

from movie_muse.editor.api import EditorService, sample_project_and_document
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService


def test_accessibility_contract_uses_layout_reading_order(tmp_path: Path) -> None:
    project, document, branch_id = sample_project_and_document()
    workspace = LocalWorkspace(tmp_path / "a11y")
    workspace.open_project(project, document, branch_id=branch_id)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=project.owner_actor_id)
    session = EditorService(revisions, actor_id=project.owner_actor_id)
    contract = session.accessibility()
    assert contract.role == "application"
    assert contract.label == "Movie Muse screenplay editor"
    assert contract.live_region == "polite"
    assert contract.reading_order
    assert any("KITCHEN" in line or "Ada" in line or "ADA" in line for line in contract.reading_order)
