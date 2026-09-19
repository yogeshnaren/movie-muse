"""Final Draft live round-trip gate. Unset binary is fail-closed, never skipped."""

from __future__ import annotations

import os
from pathlib import Path

from movie_muse.fdx.errors import FinalDraftUnavailableError, PdfImportUnavailableError
from movie_muse.fdx.types import FINAL_DRAFT_BIN_ENV
from movie_muse.schemas.api import ScreenplayDocument


def final_draft_binary() -> str | None:
    value = os.environ.get(FINAL_DRAFT_BIN_ENV, "").strip()
    return value or None


def final_draft_available() -> bool:
    binary = final_draft_binary()
    return bool(binary and Path(binary).exists())


def require_final_draft() -> str:
    binary = final_draft_binary()
    if not binary or not Path(binary).exists():
        raise FinalDraftUnavailableError(
            f"{FINAL_DRAFT_BIN_ENV} is unset or not an executable path; "
            "EXT-FDX-FINAL-DRAFT stays NOT_RUN (fail-closed, not skipped)"
        )
    return binary


def final_draft_round_trip(_document: ScreenplayDocument) -> bytes:
    """Movie Muse → FDX → Final Draft → FDX.

    Requires a licensed Final Draft binary. A mock cannot satisfy EXT-FDX-FINAL-DRAFT.
    """

    require_final_draft()
    raise FinalDraftUnavailableError(
        "Final Draft automation is not configured in this environment; "
        "EXT-FDX-FINAL-DRAFT stays NOT_RUN"
    )


def import_pdf(_data: bytes) -> None:
    raise PdfImportUnavailableError(
        "PDF import is an explicitly lossy pathway and is not available in MM-013; "
        "use FDX or Fountain/plain-text with a LossReport"
    )
