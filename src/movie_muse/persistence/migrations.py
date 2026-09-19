"""Idempotent, crash-safe forward migrations for the embedded store."""

from __future__ import annotations

import re
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

_ADD_COLUMN = re.compile(
    r"^ALTER TABLE (\w+) ADD COLUMN (\w+)\b",
    flags=re.IGNORECASE,
)


def applied_versions(connection: sqlite3.Connection) -> set[int]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchall()
    if not rows:
        return set()
    return {int(row[0]) for row in connection.execute("SELECT version FROM schema_migrations")}


def _sql_statements(sql: str) -> list[str]:
    return [part.strip() for part in sql.split(";") if part.strip()]


def _row_name(row: sqlite3.Row | tuple[object, ...], index: int = 1) -> str:
    if isinstance(row, sqlite3.Row):
        return str(row["name"])
    return str(row[index])


def column_exists(connection: sqlite3.Connection, table: str, column: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return any(_row_name(row) == column for row in rows)


def _adapt_statement(connection: sqlite3.Connection, statement: str) -> str | None:
    """Skip DDL that already landed after a crash between DDL and the version row."""

    compact = " ".join(statement.split())
    match = _ADD_COLUMN.match(compact)
    if match is None:
        return statement
    table, column = match.group(1), match.group(2)
    if column_exists(connection, table, column):
        return None
    return statement


def apply_migrations(connection: sqlite3.Connection) -> int:
    """Apply pending forward migrations.

    Each version runs inside an explicit transaction with its bookkeeping row.
    If a crash committed DDL but not the version row (SQLite may auto-commit
    some ALTER TABLE), reopen skips already-present columns and records the
    version. Re-running is therefore idempotent.
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
        statements = [
            adapted
            for statement in _sql_statements(sql)
            if (adapted := _adapt_statement(connection, statement)) is not None
        ]
        stamp = utc_now()
        try:
            connection.execute("BEGIN IMMEDIATE")
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, stamp),
            )
            connection.execute("COMMIT")
        except Exception:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        applied.add(version)
    return latest
