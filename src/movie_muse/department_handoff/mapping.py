"""Map breakdown element kinds onto craft departments."""

from __future__ import annotations

from movie_muse.breakdown.api import ElementKind

KIND_DEPARTMENT: dict[ElementKind, str] = {
    ElementKind.CAST: "casting",
    ElementKind.EXTRAS: "casting",
    ElementKind.MINOR: "casting",
    ElementKind.LOCATION: "locations",
    ElementKind.PERMIT: "locations",
    ElementKind.PROP: "props",
    ElementKind.VEHICLE: "props",
    ElementKind.WARDROBE: "costume",
    ElementKind.MAKEUP: "makeup",
    ElementKind.ANIMAL: "animals",
    ElementKind.STUNT: "stunts",
    ElementKind.SAFETY: "stunts",
    ElementKind.INTIMACY: "stunts",
    ElementKind.VFX: "vfx",
    ElementKind.SFX: "vfx",
    ElementKind.SOUND: "sound",
    ElementKind.EQUIPMENT: "camera",
    ElementKind.TIMING: "ad",
}


def department_for(kind: ElementKind) -> str:
    return KIND_DEPARTMENT[kind]


def kinds_for(department: str) -> frozenset[ElementKind]:
    return frozenset(kind for kind, name in KIND_DEPARTMENT.items() if name == department)
