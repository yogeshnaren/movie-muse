"""Public surface of ``movie_muse.adapters.google_meet``.

Hosts and other modules must import this module, never sibling internals.
EXT-GOOGLE-MEET-SANDBOX stays NOT_RUN until a real sandbox URL is recorded.
Mocks do not satisfy the live gate.
"""

from __future__ import annotations

from movie_muse.adapters.google_meet.errors import (
    GoogleMeetAdapterError,
    GoogleMeetSandboxUnavailableError,
    GoogleMeetScopeError,
    GoogleMeetTokenError,
    GoogleMeetWebhookError,
)
from movie_muse.adapters.google_meet.service import (
    GoogleMeetAdapter,
    google_meet_authorization_url,
    google_meet_sandbox_base_url,
    require_google_meet_sandbox,
    sign_google_meet_payload,
)
from movie_muse.adapters.google_meet.types import (
    GOOGLE_MEET_SANDBOX_ENV,
    LEAST_SCOPES,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    CredentialStatus,
    GoogleMeetCredential,
)

__all__ = [
    "GOOGLE_MEET_SANDBOX_ENV",
    "LEAST_SCOPES",
    "SIGNATURE_HEADER",
    "TIMESTAMP_HEADER",
    "CredentialStatus",
    "GoogleMeetAdapter",
    "GoogleMeetAdapterError",
    "GoogleMeetCredential",
    "GoogleMeetSandboxUnavailableError",
    "GoogleMeetScopeError",
    "GoogleMeetTokenError",
    "GoogleMeetWebhookError",
    "google_meet_authorization_url",
    "google_meet_sandbox_base_url",
    "require_google_meet_sandbox",
    "sign_google_meet_payload",
]
