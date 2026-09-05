"""Content-addressed input and layout hashes. Same inputs → same bytes."""

from __future__ import annotations

from typing import Any

from movie_muse.layout.metrics import FONT_METRICS_VERSION, LAYOUT_ENGINE_VERSION
from movie_muse.layout.types import PaperProfile, ProductionLockState, StyleProfile
from movie_muse.persistence.api import digest_payload
from movie_muse.schemas.api import ScreenplayDocument


def input_hash(
    document: ScreenplayDocument,
    style_profile: StyleProfile,
    paper_profile: PaperProfile,
    lock_state: ProductionLockState,
    *,
    engine_version: str = LAYOUT_ENGINE_VERSION,
    font_metrics_version: str = FONT_METRICS_VERSION,
) -> str:
    payload: dict[str, Any] = {
        "document": document.to_dict(),
        "style_profile": style_profile.to_dict(),
        "paper_profile": paper_profile.to_dict(),
        "production_lock_state": lock_state.to_dict(),
        "layout_engine_version": engine_version,
        "font_metrics_version": font_metrics_version,
    }
    _encoded, digest = digest_payload(payload)
    return digest


def hash_payload(payload: dict[str, Any]) -> str:
    _encoded, digest = digest_payload(payload)
    return digest
