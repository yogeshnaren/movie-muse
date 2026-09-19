"""Public surface of ``movie_muse.fdx``.

FDX is a compatibility adapter. ScreenplayDocument remains canonical.
EXT-FDX-FINAL-DRAFT stays NOT_RUN until a real Final Draft corpus is recorded.
Unset MOVIE_MUSE_FINAL_DRAFT_BIN fails closed with FinalDraftUnavailableError.
"""

from __future__ import annotations

from movie_muse.fdx.convert import export_fdx, import_fdx, validate_profile
from movie_muse.fdx.errors import (
    FdxError,
    FdxParseError,
    FdxProfileError,
    FinalDraftUnavailableError,
    FountainParseError,
    PdfImportUnavailableError,
    SilentLossError,
)
from movie_muse.fdx.final_draft import (
    FINAL_DRAFT_BIN_ENV,
    final_draft_available,
    require_final_draft,
)
from movie_muse.fdx.fountain import import_fountain, import_plain_text
from movie_muse.fdx.serialize import canonical_xml, parse_xml
from movie_muse.fdx.service import FdxService
from movie_muse.fdx.types import (
    ALLOWED_PARAGRAPH_TYPES,
    KIND_TO_PARAGRAPH,
    MM_NS,
    PROFILE_NAME,
    PROFILE_VERSION,
    LossItem,
    LossReport,
    LossSeverity,
)

__all__ = [
    "ALLOWED_PARAGRAPH_TYPES",
    "FINAL_DRAFT_BIN_ENV",
    "KIND_TO_PARAGRAPH",
    "MM_NS",
    "PROFILE_NAME",
    "PROFILE_VERSION",
    "FdxError",
    "FdxParseError",
    "FdxProfileError",
    "FdxService",
    "FinalDraftUnavailableError",
    "FountainParseError",
    "LossItem",
    "LossReport",
    "LossSeverity",
    "PdfImportUnavailableError",
    "SilentLossError",
    "canonical_xml",
    "export_fdx",
    "final_draft_available",
    "import_fdx",
    "import_fountain",
    "import_plain_text",
    "parse_xml",
    "require_final_draft",
    "validate_profile",
]
