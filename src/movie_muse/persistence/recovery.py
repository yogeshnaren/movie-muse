"""Corruption detection and restoration from the last known-good backup."""

from __future__ import annotations

from pathlib import Path

from movie_muse.persistence.backup import restore_backup
from movie_muse.persistence.errors import CorruptStoreError
from movie_muse.persistence.store import LocalStore


def recover_if_corrupt(store_root: Path, backup_dir: Path | None) -> LocalStore:
    """Open the store, or restore from ``backup_dir`` when integrity fails."""

    store: LocalStore | None = None
    try:
        store = LocalStore(store_root)
        store.integrity_check()
        return store
    except Exception as exc:
        if store is not None:
            store.close()
        if backup_dir is None:
            raise CorruptStoreError(
                f"store is unreadable and no backup was provided: {exc}"
            ) from exc
        restore_backup(store_root, backup_dir)
        recovered = LocalStore(store_root)
        recovered.integrity_check()
        return recovered
