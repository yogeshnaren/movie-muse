"""mypy fixture: using the matching stable-id NewType must type-check cleanly."""

from __future__ import annotations

from movie_muse.schemas.ids import SceneId


def take_scene_id(scene_id: SceneId) -> str:
    return str(scene_id)


take_scene_id(SceneId("scn_01ARZ3NDEKTSV4RRFFQ69G5FAV"))
