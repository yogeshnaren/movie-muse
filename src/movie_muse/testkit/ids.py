"""Deterministic ID minting for committed fixtures.

Schema kinds use ``new_id`` prefixes. Other identifiers use
``f"{prefix}_{new_ulid()}"``. Time and randomness are pinned so regeneration
is byte-stable.
"""

from __future__ import annotations

from movie_muse.schemas.api import ID_KIND_PREFIXES, new_ulid

FIXED_TIME_MS = 1_725_148_800_000


class IdMint:
    """Monotonic, seed-stable ULID mint for one fixture family."""

    def __init__(self, start: int) -> None:
        self._n = start

    def next_n(self) -> int:
        self._n += 1
        return self._n

    def schema(self, kind: str) -> str:
        n = self.next_n()
        if kind not in ID_KIND_PREFIXES:
            raise ValueError(f"unknown schema kind {kind!r}")
        return f"{ID_KIND_PREFIXES[kind]}_{new_ulid(_time_ms=FIXED_TIME_MS + n, _random_bytes=n.to_bytes(10, 'big'))}"

    def prefixed(self, prefix: str) -> str:
        n = self.next_n()
        return f"{prefix}_{new_ulid(_time_ms=FIXED_TIME_MS + n, _random_bytes=n.to_bytes(10, 'big'))}"
