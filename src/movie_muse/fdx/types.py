"""FDX profile types, paragraph map, and explicit loss reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from movie_muse.schemas.api import BlockKind

PROFILE_VERSION = "1.0.0"
PROFILE_NAME = "movie_muse_fdx"
DOCUMENT_TYPE = "Script"
TEMPLATE_NAME = "MovieMuse"
FDX_VERSION = "1"
MM_NS = "https://movie-muse.dev/fdx"
MM_PREFIX = "mm"
FINAL_DRAFT_BIN_ENV = "MOVIE_MUSE_FINAL_DRAFT_BIN"

KIND_TO_PARAGRAPH: dict[BlockKind, str] = {
    BlockKind.SCENE_HEADING: "Scene Heading",
    BlockKind.ACTION: "Action",
    BlockKind.CHARACTER: "Character",
    BlockKind.PARENTHETICAL: "Parenthetical",
    BlockKind.DIALOGUE: "Dialogue",
    BlockKind.TRANSITION: "Transition",
    BlockKind.SHOT: "Shot",
    BlockKind.GENERAL: "General",
    BlockKind.LYRICS: "Lyrics",
    BlockKind.PAGE_BREAK: "Page Break",
    BlockKind.TITLE_PAGE_ELEMENT: "Title",
}

PARAGRAPH_TO_KIND: dict[str, BlockKind] = {value: key for key, value in KIND_TO_PARAGRAPH.items()}

ALLOWED_PARAGRAPH_TYPES = frozenset(PARAGRAPH_TO_KIND)


class LossSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class LossItem:
    code: str
    message: str
    severity: LossSeverity = LossSeverity.WARNING
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "path": self.path,
        }


@dataclass(frozen=True, slots=True)
class LossReport:
    """User-visible disclosure of what a conversion cannot preserve.

    Empty means lossless for the Movie Muse FDX profile. Non-empty reports
    must be shown before save/export; silent drops are forbidden.
    """

    items: tuple[LossItem, ...] = ()
    pathway: str = "fdx"

    @property
    def empty(self) -> bool:
        return not self.items

    @property
    def lossless(self) -> bool:
        return self.empty

    def to_dict(self) -> dict[str, Any]:
        return {
            "pathway": self.pathway,
            "lossless": self.lossless,
            "items": [item.to_dict() for item in self.items],
        }


@dataclass
class LossAccumulator:
    pathway: str
    items: list[LossItem] = field(default_factory=list)

    def add(
        self,
        code: str,
        message: str,
        *,
        severity: LossSeverity = LossSeverity.WARNING,
        path: str | None = None,
    ) -> None:
        self.items.append(LossItem(code=code, message=message, severity=severity, path=path))

    def report(self) -> LossReport:
        return LossReport(items=tuple(self.items), pathway=self.pathway)
