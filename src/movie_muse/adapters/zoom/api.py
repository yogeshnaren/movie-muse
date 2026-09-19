"""Public surface of ``movie_muse.adapters.zoom``.

Hosts and other modules must import this module, never sibling internals.
EXT-ZOOM-SANDBOX stays NOT_RUN until a real sandbox URL is recorded.
Mocks do not satisfy the live gate.
"""

from __future__ import annotations

from movie_muse.adapters.zoom.errors import (
    ZoomAdapterError,
    ZoomSandboxUnavailableError,
    ZoomScopeError,
    ZoomTokenError,
    ZoomWebhookError,
)
from movie_muse.adapters.zoom.service import (
    ZoomAdapter,
    require_zoom_sandbox,
    sign_zoom_payload,
    zoom_authorization_url,
    zoom_sandbox_base_url,
)
from movie_muse.adapters.zoom.types import (
    LEAST_SCOPES,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    ZOOM_SANDBOX_ENV,
    CredentialStatus,
    ZoomCredential,
)

__all__ = [
    "LEAST_SCOPES",
    "SIGNATURE_HEADER",
    "TIMESTAMP_HEADER",
    "ZOOM_SANDBOX_ENV",
    "CredentialStatus",
    "ZoomAdapter",
    "ZoomAdapterError",
    "ZoomCredential",
    "ZoomSandboxUnavailableError",
    "ZoomScopeError",
    "ZoomTokenError",
    "ZoomWebhookError",
    "require_zoom_sandbox",
    "sign_zoom_payload",
    "zoom_authorization_url",
    "zoom_sandbox_base_url",
]
