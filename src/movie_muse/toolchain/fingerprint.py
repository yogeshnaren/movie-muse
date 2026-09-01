"""Commit-bound input fingerprints for work packages."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from movie_muse.toolchain.scopes import ScopeCatalog, resolve_item_paths


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_item_fingerprint(
    *,
    root: Path,
    catalog: ScopeCatalog,
    item_id: str,
    scope_keys: list[str],
    verification_commit: str,
    dependency_fingerprints: Mapping[str, str | None],
) -> tuple[str, list[str]]:
    paths = resolve_item_paths(root, catalog, scope_keys, for_fingerprint=True)
    files = [[path, sha256_file(root / path)] for path in paths]
    payload = {
        "algorithm": "sha256",
        "item_id": item_id,
        "verification_commit": verification_commit,
        "scope_keys": list(scope_keys),
        "files": files,
        "direct_dependency_fingerprints": {
            key: dependency_fingerprints[key] for key in sorted(dependency_fingerprints)
        },
    }
    return sha256_bytes(canonical_json(payload).encode("utf-8")), paths
