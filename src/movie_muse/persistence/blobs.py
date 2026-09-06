"""Content-addressed local blob files with crash-safe replace."""

from __future__ import annotations

import os
from pathlib import Path

from movie_muse.persistence.canonical import sha256_hex
from movie_muse.persistence.errors import PersistenceError


class BlobStore:
    """Stores opaque bytes under ``blobs/<sha256>`` using temp-file + fsync + rename."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, digest: str) -> Path:
        return self.root / digest

    def put(self, data: bytes, *, expected_digest: str | None = None) -> str:
        digest = sha256_hex(data)
        if expected_digest is not None and digest != expected_digest:
            raise PersistenceError("blob digest mismatch")
        destination = self.path_for(digest)
        if destination.exists():
            return digest
        tmp = destination.with_name(f".{digest}.tmp")
        with tmp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, destination)
        return digest

    def get(self, digest: str) -> bytes:
        path = self.path_for(digest)
        if not path.is_file():
            raise PersistenceError(f"missing blob {digest}")
        return path.read_bytes()

    def exists(self, digest: str) -> bool:
        return self.path_for(digest).is_file()
