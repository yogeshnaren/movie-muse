"""Thin iOS host. Mutations go through movie_muse.platforms.api only."""

from __future__ import annotations

from pathlib import Path

from movie_muse.platforms.api import PlatformApp, PlatformId, open_platform, resume_platform


def open_ios_app(home: Path) -> PlatformApp:
    return open_platform(PlatformId.IOS, home)


def resume_ios_app(home: Path) -> PlatformApp:
    return resume_platform(PlatformId.IOS, home)
