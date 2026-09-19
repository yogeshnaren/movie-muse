"""Public surface of ``movie_muse.storyboard``.

Hosts and other modules must import this module, never sibling internals.
Storyboards are linked ShotIR artifacts. Live image-provider smoke stays NOT_RUN.
"""

from __future__ import annotations

from movie_muse.director.api import AnnotationRole
from movie_muse.storyboard.errors import (
    AnnotationError,
    FrameNotFoundError,
    ImageProviderUnavailableError,
    LockedAttributeDriftError,
    StoryboardAcceptError,
    StoryboardError,
)
from movie_muse.storyboard.service import (
    StoryboardService,
    image_provider_base_url,
    require_image_provider,
)
from movie_muse.storyboard.types import (
    DISCLAIMER,
    IMAGE_PROVIDER_ENV,
    StoryboardAnnotation,
    StoryboardFrame,
    StoryboardMetrics,
)

__all__ = [
    "DISCLAIMER",
    "IMAGE_PROVIDER_ENV",
    "AnnotationError",
    "AnnotationRole",
    "FrameNotFoundError",
    "ImageProviderUnavailableError",
    "LockedAttributeDriftError",
    "StoryboardAcceptError",
    "StoryboardAnnotation",
    "StoryboardError",
    "StoryboardFrame",
    "StoryboardMetrics",
    "StoryboardService",
    "image_provider_base_url",
    "require_image_provider",
]
