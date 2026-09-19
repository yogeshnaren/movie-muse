"""Public surface of ``movie_muse.video_previs``.

Hosts and other modules must import this module, never sibling internals.
Generated video is labeled previs and is never canon. Live video-provider
smoke stays NOT_RUN.
"""

from __future__ import annotations

from movie_muse.video_previs.errors import (
    CanonPromotionError,
    ClipNotFoundError,
    ConsentRequiredError,
    QueueError,
    TimelineNotFoundError,
    VideoPrevisAcceptError,
    VideoPrevisError,
    VideoProviderUnavailableError,
)
from movie_muse.video_previs.service import (
    VideoPrevisService,
    require_video_provider,
    video_provider_base_url,
)
from movie_muse.video_previs.types import (
    CONTINUITY_LIMITATIONS,
    DISCLAIMER,
    VIDEO_PROVIDER_ENV,
    WORKER_ID,
    ConsentRecord,
    ConsentState,
    CostRange,
    IntendedEffectReview,
    PrevisTimeline,
    TimelineKind,
    VideoClip,
)

__all__ = [
    "CONTINUITY_LIMITATIONS",
    "DISCLAIMER",
    "VIDEO_PROVIDER_ENV",
    "WORKER_ID",
    "CanonPromotionError",
    "ClipNotFoundError",
    "ConsentRecord",
    "ConsentRequiredError",
    "ConsentState",
    "CostRange",
    "IntendedEffectReview",
    "PrevisTimeline",
    "QueueError",
    "TimelineKind",
    "TimelineNotFoundError",
    "VideoClip",
    "VideoPrevisAcceptError",
    "VideoPrevisError",
    "VideoPrevisService",
    "VideoProviderUnavailableError",
    "require_video_provider",
    "video_provider_base_url",
]
