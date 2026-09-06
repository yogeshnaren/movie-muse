"""Compile typed ScreenplayDocument syntax into structural entities."""

from __future__ import annotations

from collections import defaultdict

from movie_muse.compiler.errors import CompileValidationError
from movie_muse.compiler.syntax import normalize_character_name, parse_scene_heading
from movie_muse.compiler.types import (
    COMPILER_VERSION,
    CompiledEntity,
    CompiledScene,
    CompiledScreenplay,
)
from movie_muse.document.api import (
    DocumentKernelError,
    normalize,
    semantic_validate,
)
from movie_muse.schemas.api import BlockKind, ScreenplayDocument


class CompilerService:
    """Deterministic syntax compiler. It never calls a model."""

    version = COMPILER_VERSION

    def compile(self, document: ScreenplayDocument) -> CompiledScreenplay:
        try:
            normalized = normalize(document)
            semantic_validate(normalized)
        except DocumentKernelError as exc:
            raise CompileValidationError(str(exc)) from exc

        scenes: list[CompiledScene] = []
        characters: dict[str, list[str]] = defaultdict(list)
        character_blocks: dict[str, list[str]] = defaultdict(list)
        locations: dict[str, list[str]] = defaultdict(list)
        location_blocks: dict[str, list[str]] = defaultdict(list)
        scene_blocks: dict[str, list[str]] = defaultdict(list)
        scene_characters: dict[str, list[str]] = defaultdict(list)
        headings: dict[str, tuple[str, str | None, str | None, str | None, str | None, str]] = {}
        current_scene: str | None = None

        for block in normalized.blocks:
            if block.kind is BlockKind.SCENE_HEADING:
                current_scene = block.scene_id or block.id
                int_ext, location, time_of_day = parse_scene_heading(block.text)
                headings[current_scene] = (
                    block.text,
                    int_ext,
                    location,
                    time_of_day,
                    block.scene_number,
                    block.id,
                )
                scene_blocks[current_scene].append(block.id)
                if location:
                    if current_scene not in locations[location]:
                        locations[location].append(current_scene)
                    location_blocks[location].append(block.id)
                continue
            if current_scene is None:
                continue
            scene_blocks[current_scene].append(block.id)
            if block.kind is not BlockKind.CHARACTER:
                continue
            name = normalize_character_name(block.text)
            if not name:
                continue
            if name not in scene_characters[current_scene]:
                scene_characters[current_scene].append(name)
            if current_scene not in characters[name]:
                characters[name].append(current_scene)
            character_blocks[name].append(block.id)

        for scene_id, heading in headings.items():
            text, int_ext, location, time_of_day, scene_number, heading_block_id = heading
            scenes.append(
                CompiledScene(
                    scene_id=scene_id,
                    heading=text,
                    int_ext=int_ext,
                    location=location,
                    time_of_day=time_of_day,
                    scene_number=scene_number,
                    heading_block_id=heading_block_id,
                    character_names=tuple(scene_characters[scene_id]),
                    block_ids=tuple(scene_blocks[scene_id]),
                )
            )

        props: dict[str, list[str]] = defaultdict(list)
        prop_blocks: dict[str, list[str]] = defaultdict(list)
        block_scene = {
            block_id: scene.scene_id for scene in scenes for block_id in scene.block_ids
        }
        for tag in normalized.production_tags:
            if tag.tag_type != "prop":
                continue
            name = tag.value.strip().upper()
            if not name:
                continue
            tagged_scene = block_scene.get(tag.block_id)
            if tagged_scene is None:
                prop_blocks[name].append(tag.block_id)
                continue
            if tagged_scene not in props[name]:
                props[name].append(tagged_scene)
            prop_blocks[name].append(tag.block_id)

        entities = [
            CompiledEntity(
                kind="character",
                canonical_name=name,
                scene_ids=tuple(scene_ids),
                mention_block_ids=tuple(character_blocks[name]),
            )
            for name, scene_ids in sorted(characters.items())
        ]
        entities.extend(
            CompiledEntity(
                kind="location",
                canonical_name=name,
                scene_ids=tuple(scene_ids),
                mention_block_ids=tuple(location_blocks[name]),
            )
            for name, scene_ids in sorted(locations.items())
        )
        entities.extend(
            CompiledEntity(
                kind="prop",
                canonical_name=name,
                scene_ids=tuple(scene_ids),
                mention_block_ids=tuple(prop_blocks[name]),
            )
            for name, scene_ids in sorted(props.items())
        )
        entities.extend(
            CompiledEntity(
                kind="scene",
                canonical_name=scene.heading,
                scene_ids=(scene.scene_id,),
                mention_block_ids=(scene.heading_block_id,),
            )
            for scene in scenes
        )
        revision_id = normalized.base_revision_id or normalized.id
        return CompiledScreenplay(
            project_id=normalized.project_id,
            document_id=normalized.id,
            source_revision_id=revision_id,
            compiler_version=COMPILER_VERSION,
            scenes=tuple(scenes),
            entities=tuple(entities),
            scene_order=tuple(scene.scene_id for scene in scenes),
        )
