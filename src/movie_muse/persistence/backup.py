"""Backup and restore of the embedded database plus content-addressed blobs."""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

from movie_muse.persistence.canonical import utc_now
from movie_muse.persistence.errors import BackupError
from movie_muse.persistence.store import BLOBS_DIR, DB_NAME, LocalStore

MANIFEST_NAME = "backup_manifest.json"


def create_backup(store: LocalStore, destination: Path) -> Path:
    """Write a consistent backup directory: sqlite snapshot + blobs + manifest."""

    destination.mkdir(parents=True, exist_ok=True)
    db_copy = destination / DB_NAME
    blobs_copy = destination / BLOBS_DIR
    try:
        store.integrity_check()
        with sqlite3.connect(str(db_copy)) as backup_conn:
            store._connection.backup(backup_conn)
        if (store.root / BLOBS_DIR).exists():
            if blobs_copy.exists():
                shutil.rmtree(blobs_copy)
            shutil.copytree(store.root / BLOBS_DIR, blobs_copy)
        manifest = {
            "created_at": utc_now(),
            "schema_version": store.schema_version(),
            "db": DB_NAME,
            "blobs": BLOBS_DIR,
        }
        (destination / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    except Exception as exc:
        raise BackupError(str(exc)) from exc
    return destination


def restore_backup(store_root: Path, backup_dir: Path) -> None:
    """Replace a workspace directory with a previously created backup."""

    backup_db = backup_dir / DB_NAME
    if not backup_db.is_file():
        raise BackupError("backup is missing the sqlite database")
    store_root.mkdir(parents=True, exist_ok=True)
    target_db = store_root / DB_NAME
    tmp_db = store_root / f".{DB_NAME}.restore"
    shutil.copy2(backup_db, tmp_db)
    tmp_db.replace(target_db)
    backup_blobs = backup_dir / BLOBS_DIR
    target_blobs = store_root / BLOBS_DIR
    if backup_blobs.exists():
        if target_blobs.exists():
            shutil.rmtree(target_blobs)
        shutil.copytree(backup_blobs, target_blobs)
