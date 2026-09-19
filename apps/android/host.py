"""Thin Android host. Mutations go through movie_muse.platforms.api only."""

from __future__ import annotations

from pathlib import Path

from movie_muse.platforms.api import PlatformApp, PlatformId, open_platform, resume_platform


def open_android_app(home: Path) -> PlatformApp:
    return open_platform(PlatformId.ANDROID, home)


def resume_android_app(home: Path) -> PlatformApp:
    return resume_platform(PlatformId.ANDROID, home)
