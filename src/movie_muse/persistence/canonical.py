"""Canonical JSON bytes and content-addressed digests for persisted documents."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    """Deterministic UTF-8 JSON used as the blob identity."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_payload(payload: dict[str, Any]) -> tuple[bytes, str]:
    encoded = canonical_bytes(payload)
    return encoded, sha256_hex(encoded)
