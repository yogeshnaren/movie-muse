"""Thin Web host. Mutations go through movie_muse.platforms.api only."""

from __future__ import annotations

from pathlib import Path

from movie_muse.platforms.api import PlatformApp, PlatformId, open_platform, resume_platform


def open_web_app(home: Path, *, origin: str | None = None) -> PlatformApp:
    kwargs = {} if origin is None else {"origin": origin}
    return open_platform(PlatformId.WEB, home, **kwargs)


def resume_web_app(home: Path, *, origin: str | None = None) -> PlatformApp:
    kwargs = {} if origin is None else {"origin": origin}
    return resume_platform(PlatformId.WEB, home, **kwargs)
