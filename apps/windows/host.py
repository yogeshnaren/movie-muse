"""Thin Windows host. Mutations go through movie_muse.platforms.api only."""

from __future__ import annotations

from pathlib import Path

from movie_muse.platforms.api import PlatformApp, PlatformId, open_platform, resume_platform


def open_windows_app(home: Path) -> PlatformApp:
    return open_platform(PlatformId.WINDOWS, home)


def resume_windows_app(home: Path) -> PlatformApp:
    return resume_platform(PlatformId.WINDOWS, home)
