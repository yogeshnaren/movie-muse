"""Pinned paper and style catalogs. Unknown ids fail closed."""

from __future__ import annotations

from movie_muse.layout.errors import UnknownProfileError
from movie_muse.layout.metrics import FONT_FAMILY, FONT_METRICS_VERSION, POINT_SIZE
from movie_muse.layout.types import PaperProfile, StyleProfile

US_LETTER = PaperProfile(
    id="us_letter",
    width_in=8.5,
    height_in=11.0,
    top_margin_in=1.0,
    bottom_margin_in=1.0,
    left_margin_in=1.5,
    right_margin_in=1.0,
)

A4 = PaperProfile(
    id="a4",
    width_in=8.27,
    height_in=11.69,
    top_margin_in=1.0,
    bottom_margin_in=1.0,
    left_margin_in=1.5,
    right_margin_in=0.77,
)

PAPER_PROFILES: dict[str, PaperProfile] = {
    US_LETTER.id: US_LETTER,
    A4.id: A4,
    "letter": US_LETTER,
}

STANDARD_SCREENPLAY = StyleProfile(
    id="standard_screenplay",
    font_family=FONT_FAMILY,
    font_metrics_version=FONT_METRICS_VERSION,
    point_size=POINT_SIZE,
)

PRODUCTION_SCREENPLAY = StyleProfile(
    id="production_screenplay",
    font_family=FONT_FAMILY,
    font_metrics_version=FONT_METRICS_VERSION,
    point_size=POINT_SIZE,
)

STYLE_PROFILES: dict[str, StyleProfile] = {
    STANDARD_SCREENPLAY.id: STANDARD_SCREENPLAY,
    PRODUCTION_SCREENPLAY.id: PRODUCTION_SCREENPLAY,
}


def resolve_paper_profile(paper_profile: PaperProfile | str | None) -> PaperProfile:
    if isinstance(paper_profile, PaperProfile):
        return paper_profile
    key = paper_profile or "us_letter"
    profile = PAPER_PROFILES.get(key)
    if profile is None:
        raise UnknownProfileError(f"unknown paper profile: {key!r}")
    return profile


def resolve_style_profile(style_profile: StyleProfile | str | None) -> StyleProfile:
    if isinstance(style_profile, StyleProfile):
        return style_profile
    key = style_profile or "standard_screenplay"
    profile = STYLE_PROFILES.get(key)
    if profile is None:
        raise UnknownProfileError(f"unknown style profile: {key!r}")
    return profile
