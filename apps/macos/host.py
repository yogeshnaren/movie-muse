"""Thin macOS host. Mutations go through movie_muse.platforms.api only."""

from __future__ import annotations

from pathlib import Path

from movie_muse.platforms.api import PlatformApp, PlatformId, open_platform, resume_platform


def open_macos_app(home: Path) -> PlatformApp:
    return open_platform(PlatformId.MACOS, home)


def resume_macos_app(home: Path) -> PlatformApp:
    return resume_platform(PlatformId.MACOS, home)
