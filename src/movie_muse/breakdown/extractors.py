"""Deterministic keyword extractors for production categories."""

from __future__ import annotations

from movie_muse.breakdown.types import ElementKind
from movie_muse.schemas.api import Block, BlockKind, ScreenplayDocument

# Original cue phrases, not third-party catalog text.
CATEGORY_CUES: dict[ElementKind, tuple[str, ...]] = {
    ElementKind.EXTRAS: ("crowd", "extras", "passersby", "background players"),
    ElementKind.WARDROBE: ("coat", "uniform", "dress", "wardrobe"),
    ElementKind.MAKEUP: ("blood", "bruise", "prosthetic", "aging makeup"),
    ElementKind.VEHICLE: ("car", "truck", "van", "ferry", "motorcycle"),
    ElementKind.ANIMAL: ("horse", "dog", "cat", "bird"),
    ElementKind.STUNT: ("fight", "fall from", "crash", "stunt"),
    ElementKind.INTIMACY: ("kiss", "undress", "intimate"),
    ElementKind.MINOR: ("child", "kid", "teen", "minor"),
    ElementKind.VFX: ("cgi", "green screen", "digital double"),
    ElementKind.SFX: ("practical explosion", "squib", "pyrotechnic"),
    ElementKind.SOUND: ("radio", "horn", "needle drop", "playback"),
    ElementKind.EQUIPMENT: ("crane", "generator", "camera car"),
    ElementKind.PERMIT: ("street closure", "permit", "police detail"),
    ElementKind.SAFETY: ("weapon", "live fire", "water work", "safety"),
}


def scan_cues(
    document: ScreenplayDocument,
) -> dict[ElementKind, list[tuple[str, Block]]]:
    hits: dict[ElementKind, list[tuple[str, Block]]] = {kind: [] for kind in CATEGORY_CUES}
    for block in document.blocks:
        if block.kind not in {BlockKind.ACTION, BlockKind.DIALOGUE, BlockKind.SCENE_HEADING}:
            continue
        lowered = block.text.lower()
        for kind, cues in CATEGORY_CUES.items():
            for cue in cues:
                if cue in lowered:
                    hits[kind].append((cue, block))
                    break
    return hits
