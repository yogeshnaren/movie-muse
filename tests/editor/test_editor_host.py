"""The editor host binds EditorService over an already-local workspace."""

from __future__ import annotations

from pathlib import Path

from apps.editor.host import bind_existing_workspace, open_editor_session

from movie_muse.editor.api import sample_project_and_document


def test_host_opens_and_resumes_offline(tmp_path: Path) -> None:
    project, document, branch_id = sample_project_and_document()
    root = tmp_path / "host-ws"
    session = open_editor_session(
        root,
        project=project,
        document=document,
        branch_id=branch_id,
        actor_id=project.owner_actor_id,
    )
    session.set_airplane(True)
    action = document.blocks[1]
    session.update_text(action.id, "Host saved locally.")
    session.revisions.workspace.close()
    resumed = bind_existing_workspace(root, actor_id=project.owner_actor_id)
    assert resumed.document().blocks[1].text == "Host saved locally."
    assert resumed.outline()
