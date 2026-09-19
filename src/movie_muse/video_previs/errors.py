"""Typed failures for video previs queue, consent, and live-provider gates."""

from __future__ import annotations


class VideoPrevisError(RuntimeError):
    """Base class for video previs failures."""


class ClipNotFoundError(VideoPrevisError):
    """The named previs clip is not in the index."""


class TimelineNotFoundError(VideoPrevisError):
    """The named previs timeline is not in the index."""


class ConsentRequiredError(VideoPrevisError):
    """Queued or live video previs requires visible granted consent."""


class VideoProviderUnavailableError(VideoPrevisError):
    """Live video-provider smoke is fail-closed; mocks do not satisfy the gate."""


class VideoPrevisAcceptError(VideoPrevisError):
    """Only a human principal may accept or review previs assets."""


class CanonPromotionError(VideoPrevisError):
    """Generated video is never canon by itself."""


class QueueError(VideoPrevisError):
    """Durable queue operations failed closed."""
