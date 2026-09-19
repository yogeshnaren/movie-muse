"""Public surface of ``movie_muse.correspondence``.

Hosts and other modules must import this module, never sibling internals.
No message sends without explicit authorized action after preview.
"""

from __future__ import annotations

from movie_muse.correspondence.errors import (
    ChannelNotConfiguredError,
    CorrespondenceError,
    DraftNotFoundError,
    PreviewRequiredError,
    SendNotAuthorizedError,
)
from movie_muse.correspondence.service import CorrespondenceService
from movie_muse.correspondence.types import MessageDraft, MessagePreview, SendResult

__all__ = [
    "ChannelNotConfiguredError",
    "CorrespondenceError",
    "CorrespondenceService",
    "DraftNotFoundError",
    "MessageDraft",
    "MessagePreview",
    "PreviewRequiredError",
    "SendNotAuthorizedError",
    "SendResult",
]
