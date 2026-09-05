"""LayoutService: the public application entry for deterministic pagination."""

from __future__ import annotations

from movie_muse.layout.engine import layout_document
from movie_muse.layout.locks import lock_state_from_document
from movie_muse.layout.metrics import FONT_METRICS_VERSION, LAYOUT_ENGINE_VERSION
from movie_muse.layout.profiles import resolve_paper_profile, resolve_style_profile
from movie_muse.layout.render import reading_order_text, render_result
from movie_muse.layout.types import (
    LayoutResult,
    PaperProfile,
    ProductionLockState,
    StyleProfile,
)
from movie_muse.schemas.api import ScreenplayDocument


class LayoutService:
    """Canonical paginator. Editor/browser measurement cannot replace this."""

    engine_version = LAYOUT_ENGINE_VERSION
    font_metrics_version = FONT_METRICS_VERSION

    def layout(
        self,
        document: ScreenplayDocument,
        style_profile: StyleProfile | str | None = None,
        paper_profile: PaperProfile | str | None = None,
        production_lock_state: ProductionLockState | None = None,
        engine_version: str = LAYOUT_ENGINE_VERSION,
    ) -> LayoutResult:
        return layout_document(
            document,
            style_profile=style_profile,
            paper_profile=paper_profile,
            production_lock_state=production_lock_state,
            engine_version=engine_version,
        )

    def lock_state(self, document: ScreenplayDocument) -> ProductionLockState:
        return lock_state_from_document(document)

    def resolve_style(self, style_profile: StyleProfile | str | None) -> StyleProfile:
        return resolve_style_profile(style_profile)

    def resolve_paper(self, paper_profile: PaperProfile | str | None) -> PaperProfile:
        return resolve_paper_profile(paper_profile)

    def render_text(self, result: LayoutResult, paper_profile: PaperProfile | str | None = None) -> str:
        paper = resolve_paper_profile(paper_profile or result.paper_profile_id)
        return render_result(result, paper)

    def reading_order(self, result: LayoutResult) -> str:
        return reading_order_text(result)
