"""Embedded transactional SQLite store for local-first authoring."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from movie_muse.persistence.blobs import BlobStore
from movie_muse.persistence.canonical import utc_now
from movie_muse.persistence.errors import CorruptStoreError, PersistenceError
from movie_muse.persistence.migrations import CURRENT_SCHEMA_VERSION, apply_migrations

DB_NAME = "movie_muse.sqlite"
BLOBS_DIR = "blobs"

DEFAULT_FLAGS = {
    "auth_outage": 0,
    "subscription_outage": 0,
    "sync_outage": 0,
    "ai_outage": 0,
    "connectivity_offline": 0,
}


class LocalStore:
    """Authoritative on-device store. Network is never required to open it."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / DB_NAME
        self.blobs = BlobStore(self.root / BLOBS_DIR)
        self._connection = sqlite3.connect(str(self.db_path), isolation_level=None)
        self._connection.row_factory = sqlite3.Row
        self._configure()
        apply_migrations(self._connection)
        self._seed_flags()

    def _configure(self) -> None:
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA temp_store=MEMORY")

    def _seed_flags(self) -> None:
        for name, value in DEFAULT_FLAGS.items():
            self._connection.execute(
                "INSERT OR IGNORE INTO capability_flags(name, value) VALUES (?, ?)",
                (name, value),
            )

    def close(self) -> None:
        self._connection.close()

    def integrity_check(self) -> str:
        row = self._connection.execute("PRAGMA integrity_check").fetchone()
        result = str(row[0]) if row is not None else "failed"
        if result != "ok":
            raise CorruptStoreError(result)
        return result

    def schema_version(self) -> int:
        row = self._connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        if row is None or row[0] is None:
            raise PersistenceError("schema migrations table is empty")
        version = int(row[0])
        if version != CURRENT_SCHEMA_VERSION:
            raise PersistenceError(f"unexpected schema version {version}")
        return version

    def set_flag(self, name: str, enabled: bool) -> None:
        if name not in DEFAULT_FLAGS:
            raise PersistenceError(f"unknown capability flag: {name}")
        self._connection.execute(
            "UPDATE capability_flags SET value=? WHERE name=?",
            (1 if enabled else 0, name),
        )

    def flags(self) -> dict[str, bool]:
        rows = self._connection.execute("SELECT name, value FROM capability_flags").fetchall()
        return {str(row["name"]): bool(row["value"]) for row in rows}

    def local_work_allowed(self) -> bool:
        """Auth/subscription/sync/AI/network outages never lock already-local work."""

        return True

    def sync_upload_allowed(self) -> bool:
        flags = self.flags()
        return not (
            flags["connectivity_offline"]
            or flags["sync_outage"]
            or flags["auth_outage"]
            or flags["subscription_outage"]
        )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield self._connection
            self._connection.execute("COMMIT")
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    def put_blob(self, data: bytes, *, expected_digest: str | None = None) -> str:
        digest = self.blobs.put(data, expected_digest=expected_digest)
        self._connection.execute(
            "INSERT OR IGNORE INTO blobs_index(digest, size, created_at) VALUES (?, ?, ?)",
            (digest, len(data), utc_now()),
        )
        return digest

    def get_blob(self, digest: str) -> bytes:
        return self.blobs.get(digest)

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        return self._connection.execute(sql, params)

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        row = self._connection.execute(sql, params).fetchone()
        return row if row is not None else None

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return list(self._connection.execute(sql, params).fetchall())

    def set_meta(self, key: str, value: str) -> None:
        self._connection.execute(
            "INSERT INTO workspace_meta(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def get_meta(self, key: str) -> str | None:
        row = self.fetchone("SELECT value FROM workspace_meta WHERE key=?", (key,))
        return None if row is None else str(row["value"])

