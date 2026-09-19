"""Typed failures for the Zoom adapter. Live sandbox absence is fail-closed."""

from __future__ import annotations


class ZoomAdapterError(RuntimeError):
    """Base class for Zoom adapter failures."""


class ZoomSandboxUnavailableError(ZoomAdapterError):
    """EXT-ZOOM-SANDBOX stays NOT_RUN when the sandbox URL is unset."""


class ZoomTokenError(ZoomAdapterError):
    """Expired or revoked credentials cannot import recordings."""


class ZoomWebhookError(ZoomAdapterError):
    """Signed webhook validation or replay protection failed."""


class ZoomScopeError(ZoomAdapterError):
    """Only the declared least-privilege Zoom scopes may be stored."""
