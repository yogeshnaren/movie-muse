"""Idempotent, crash-safe forward migrations for the embedded store."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from movie_muse.persistence.canonical import utc_now
from movie_muse.persistence.errors import MigrationError

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    head_revision_id TEXT,
    payload_digest TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS revisions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    branch_id TEXT NOT NULL,
    parent_revision_id TEXT,
    blob_digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    actor_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS blobs_index (
    digest TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outbox (
    operation_id TEXT PRIMARY KEY,
    envelope_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inbox (
    operation_id TEXT PRIMARY KEY,
    envelope_json TEXT NOT NULL,
    status TEXT NOT NULL,
    received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS capability_flags (
    name TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS workspace_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

SCHEMA_V2 = """
ALTER TABLE documents ADD COLUMN last_export_at TEXT;
"""

MIGRATIONS: Sequence[tuple[int, str, str]] = (
    (1, "initial_local_store", SCHEMA_V1),
    (2, "documents_last_export_at", SCHEMA_V2),
)

CURRENT_SCHEMA_VERSION = MIGRATIONS[-1][0]


def applied_versions(connection: sqlite3.Connection) -> set[int]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchall()
    if not rows:
        return set()
    return {int(row[0]) for row in connection.execute("SELECT version FROM schema_migrations")}


def apply_migrations(connection: sqlite3.Connection) -> int:
    """Apply pending forward migrations.

    Each version is one ``executescript`` including the migrations-table insert so
    a crash cannot record a version that did not apply. Re-open retries the
    unfinished version. Already-applied versions are skipped.
    """

    connection.execute("PRAGMA foreign_keys=ON")
    applied = applied_versions(connection)
    latest = 0
    for version, name, sql in MIGRATIONS:
        latest = version
        if version in applied:
            continue
        if version > 1 and (version - 1) not in applied:
            raise MigrationError(f"missing predecessor migration for v{version}")
        stamp = utc_now()
        # executescript issues COMMIT of any pending txn, then runs the script.
        connection.executescript(
            sql
            + (
                "INSERT INTO schema_migrations(version, name, applied_at) "
                f"VALUES ({int(version)}, '{name}', '{stamp}');"
            )
        )
        applied.add(version)
    return latest
