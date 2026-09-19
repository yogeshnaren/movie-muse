"""Deterministic heading and character compile from the document kernel."""

from __future__ import annotations

from movie_muse.compiler.api import CompilerService, parse_scene_heading
from movie_muse.editor.api import sample_project_and_document
from movie_muse.testkit.api import FixtureCatalog


def test_parse_scene_heading_int_kitchen() -> None:
    int_ext, location, time_of_day = parse_scene_heading("INT. KITCHEN - DAY")
    assert int_ext == "INT."
    assert location == "KITCHEN"
    assert time_of_day == "DAY"


def test_compile_sample_finds_character_and_location() -> None:
    project, document, _branch = sample_project_and_document()
    compiled = CompilerService().compile(document)
    assert compiled.project_id == project.id
    assert compiled.compiler_version == "1.0.0"
    names = {(entity.kind, entity.canonical_name) for entity in compiled.entities}
    assert ("character", "ADA") in names
    assert ("location", "KITCHEN") in names
    assert compiled.scene_order
    assert all(scene.heading_block_id for scene in compiled.scenes)


def test_compile_small_kitchen_fixture_is_deterministic() -> None:
    catalog = FixtureCatalog()
    document = catalog.get("small_kitchen").document
    compiler = CompilerService()
    first = compiler.compile(document)
    second = compiler.compile(document)
    assert first.to_dict() == second.to_dict()
    kinds = {entity.kind for entity in first.entities}
    assert "scene" in kinds
    assert "location" in kinds
