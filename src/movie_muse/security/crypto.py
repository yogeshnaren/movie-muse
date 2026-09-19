"""Authenticated encryption with stdlib SHA-256 (no extra crypto dependency)."""

from __future__ import annotations

import hashlib
import hmac
import os
from base64 import b64decode, b64encode

from movie_muse.security.errors import IntegrityError, KeyUnavailableError
from movie_muse.security.types import SealedBlob

_MAC_LEN = 32


def derive_workspace_key(workspace_id: str, *, salt: bytes = b"movie-muse-v21") -> bytes:
    return hashlib.pbkdf2_hmac("sha256", workspace_id.encode(), salt, 120_000, dklen=32)


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def seal(plaintext: bytes, key: bytes | None, *, byok: bool) -> SealedBlob:
    if not key:
        raise KeyUnavailableError("no local or customer key is configured")
    nonce = os.urandom(16)
    stream = _keystream(key, nonce, len(plaintext))
    cipher = bytes(a ^ b for a, b in zip(plaintext, stream, strict=True))
    mac = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    return SealedBlob(
        nonce=b64encode(nonce).decode("ascii"),
        ciphertext=b64encode(cipher).decode("ascii"),
        mac=b64encode(mac).decode("ascii"),
        byok=byok,
    )


def unseal(blob: SealedBlob, key: bytes | None) -> bytes:
    if not key:
        raise KeyUnavailableError("no local or customer key is configured")
    nonce = b64decode(blob.nonce.encode("ascii"))
    cipher = b64decode(blob.ciphertext.encode("ascii"))
    expected = b64decode(blob.mac.encode("ascii"))
    actual = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    if len(expected) != _MAC_LEN or not hmac.compare_digest(expected, actual):
        raise IntegrityError("sealed payload MAC did not verify")
    stream = _keystream(key, nonce, len(cipher))
    return bytes(a ^ b for a, b in zip(cipher, stream, strict=True))
