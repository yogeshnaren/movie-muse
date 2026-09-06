"""Local outbox/inbox sync primitives (MM-004).

Domain commands persist through ``movie_muse.persistence.api``. This module
moves idempotent envelopes; it does not last-writer-wins merge.
"""

from __future__ import annotations
