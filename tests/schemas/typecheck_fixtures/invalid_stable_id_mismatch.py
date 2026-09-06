"""mypy fixture: passing a NoteId where a SceneId is required MUST fail.

Stable IDs are distinct ``NewType``s per entity kind (MM-002 acceptance
criterion 3); mypy must reject mixing them even though both are ``str`` at
runtime. See ``tests/schemas/test_typecheck_fixtures.py``.
"""

from __future__ import annotations

from movie_muse.schemas.ids import NoteId, SceneId


def take_scene_id(scene_id: SceneId) -> str:
    return str(scene_id)


note_id = NoteId("note_01ARZ3NDEKTSV4RRFFQ69G5FAV")
take_scene_id(note_id)
