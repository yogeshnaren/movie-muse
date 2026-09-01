"""Repeated-build nondeterminism detection."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from movie_muse.persistence.api import digest_payload
from movie_muse.testkit.errors import NondeterminismError


class NondeterminismGuard:
    """Run a loader/hasher N times and fail if any digest differs."""

    def assert_stable(
        self,
        producer: Callable[[], Any],
        *,
        times: int = 5,
        label: str = "build",
    ) -> str:
        if times < 2:
            raise ValueError("nondeterminism detection requires at least two runs")
        digests: list[str] = []
        for _ in range(times):
            value = producer()
            payload = _as_payload(value)
            _encoded, digest = digest_payload(payload)
            digests.append(digest)
        unique = set(digests)
        if len(unique) != 1:
            raise NondeterminismError(
                f"{label} produced {len(unique)} distinct digests over {times} runs: {sorted(unique)}"
            )
        return digests[0]


def _as_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        converted = value.to_dict()
        if isinstance(converted, dict):
            return converted
    if isinstance(value, str):
        return {"digest": value}
    raise TypeError(f"cannot canonicalize {type(value).__name__} for nondeterminism hashing")
