"""Deterministic scene-heading and character-cue syntax. No model."""

from __future__ import annotations

import re

_HEADING = re.compile(
    r"^(?P<int_ext>INT\.?/EXT\.?|I/?E|INT\.?|EXT\.?)\s+(?P<location>.+?)"
    r"(?:\s+-\s+(?P<time>.+))?$",
    re.IGNORECASE,
)
_CUE_SUFFIX = re.compile(
    r"\s*(\((V\.?O\.?|O\.?S\.?|CONT'D|O\.C\.)\)|\^)\s*$",
    re.IGNORECASE,
)


def parse_scene_heading(text: str) -> tuple[str | None, str | None, str | None]:
    stripped = " ".join(text.strip().split())
    match = _HEADING.match(stripped)
    if match is None:
        return None, None, None
    int_ext = match.group("int_ext").upper().replace(" ", "")
    if int_ext in {"I/E", "INT./EXT", "INT/EXT", "INT./EXT."}:
        int_ext = "INT./EXT."
    elif int_ext.startswith("INT"):
        int_ext = "INT."
    else:
        int_ext = "EXT."
    location = match.group("location").strip().upper()
    time_raw = match.group("time")
    time_of_day = time_raw.strip().upper() if time_raw else None
    return int_ext, location, time_of_day


def normalize_character_name(text: str) -> str:
    return _CUE_SUFFIX.sub("", text.strip()).strip().upper()
