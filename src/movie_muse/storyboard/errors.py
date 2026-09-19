"""Typed failures for storyboard generation and annotation."""

from __future__ import annotations


class StoryboardError(RuntimeError):
    """Base class for storyboard failures."""


class FrameNotFoundError(StoryboardError):
    """The named storyboard frame is not in the index."""


class LockedAttributeDriftError(StoryboardError):
    """A locked ShotIR attribute must not drift in a storyboard edit."""


class ImageProviderUnavailableError(StoryboardError):
    """Live image-provider smoke is fail-closed; mocks do not satisfy the gate."""


class StoryboardAcceptError(StoryboardError):
    """Only a human principal may accept a storyboard asset."""


class AnnotationError(StoryboardError):
    """Director, producer, and writer annotations stay distinct."""
