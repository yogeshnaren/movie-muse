"""Verification scope mapping and changed-file classification."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from movie_muse.toolchain.yamlio import load_mapping

SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "coverage",
}


@dataclass(frozen=True)
class ScopeDefinition:
    key: str
    owned: tuple[str, ...]
    shared: tuple[str, ...]
    fingerprint: bool = True


@dataclass(frozen=True)
class ScopeCatalog:
    unmatched_paths_fail: bool
    empty_owned_fail_statuses: tuple[str, ...]
    fingerprint_exclude_globs: tuple[str, ...]
    shared_ignore_globs: tuple[str, ...]
    scopes: dict[str, ScopeDefinition]


def load_scope_catalog(root: Path, path: Path | None = None) -> ScopeCatalog:
    mapping = load_mapping(path or (root / "config" / "verification-scopes.yaml"))
    empty_rule = mapping.get("empty_owned_paths_fail_when_item_exists") or {}
    statuses = tuple(empty_rule.get("statuses") or ())
    scopes: dict[str, ScopeDefinition] = {}
    raw_scopes = mapping.get("scopes") or {}
    if not isinstance(raw_scopes, dict):
        raise ValueError("verification-scopes.yaml scopes must be a mapping")
    for key, raw in raw_scopes.items():
        if not isinstance(raw, dict):
            raise ValueError(f"scope {key} must be a mapping")
        scopes[str(key)] = ScopeDefinition(
            key=str(key),
            owned=tuple(str(item) for item in (raw.get("owned") or [])),
            shared=tuple(str(item) for item in (raw.get("shared") or [])),
            fingerprint=bool(raw.get("fingerprint", True)),
        )
    return ScopeCatalog(
        unmatched_paths_fail=bool(mapping.get("unmatched_paths_fail", True)),
        empty_owned_fail_statuses=statuses,
        fingerprint_exclude_globs=tuple(
            str(item) for item in (mapping.get("fingerprint_exclude_globs") or [])
        ),
        shared_ignore_globs=tuple(str(item) for item in (mapping.get("shared_ignore_globs") or [])),
        scopes=scopes,
    )


def posix_relpath(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def matches_any(path: str, globs: Iterable[str]) -> bool:
    posix = path.replace("\\", "/")
    for pattern in globs:
        normalized = pattern.replace("\\", "/")
        if fnmatch(posix, normalized) or fnmatch(posix, normalized.rstrip("/")):
            return True
        if normalized.endswith("/**") and (
            posix == normalized[:-3] or posix.startswith(normalized[:-2])
        ):
            return True
    return False


def expand_globs(root: Path, patterns: Iterable[str], exclude_globs: Iterable[str]) -> list[str]:
    found: set[str] = set()
    for pattern in patterns:
        for match in root.glob(pattern):
            if not match.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in match.relative_to(root).parts):
                continue
            rel = posix_relpath(root, match)
            if matches_any(rel, exclude_globs):
                continue
            found.add(rel)
    return sorted(found)


def scope_paths(
    root: Path,
    catalog: ScopeCatalog,
    scope: ScopeDefinition,
    *,
    include_shared: bool,
    for_fingerprint: bool,
) -> list[str]:
    patterns = list(scope.owned)
    if include_shared:
        patterns.extend(scope.shared)
    exclude = list(catalog.fingerprint_exclude_globs) if for_fingerprint else []
    if for_fingerprint and not scope.fingerprint:
        return []
    return expand_globs(root, patterns, exclude)


def classify_path(catalog: ScopeCatalog, relpath: str) -> list[str]:
    if matches_any(relpath, catalog.shared_ignore_globs):
        return []
    if matches_any(relpath, catalog.fingerprint_exclude_globs):
        matched = [
            key
            for key, scope in catalog.scopes.items()
            if matches_any(relpath, scope.owned) or matches_any(relpath, scope.shared)
        ]
        if matched:
            return matched
    keys: list[str] = []
    for key, scope in catalog.scopes.items():
        if matches_any(relpath, scope.owned) or matches_any(relpath, scope.shared):
            keys.append(key)
    return keys


def map_files_to_scopes(
    catalog: ScopeCatalog,
    relpaths: Iterable[str],
) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    unmatched: list[str] = []
    for relpath in relpaths:
        posix = PurePosixPath(relpath).as_posix()
        if matches_any(posix, catalog.shared_ignore_globs):
            continue
        keys = classify_path(catalog, posix)
        if not keys:
            unmatched.append(posix)
            continue
        mapping[posix] = keys
    if catalog.unmatched_paths_fail and unmatched:
        raise ValueError("changed files match no verification scope: " + ", ".join(unmatched))
    return mapping


def item_scope_definitions(catalog: ScopeCatalog, scope_keys: Iterable[str]) -> list[ScopeDefinition]:
    missing = [key for key in scope_keys if key not in catalog.scopes]
    if missing:
        raise ValueError(f"unknown scope keys: {missing}")
    return [catalog.scopes[key] for key in scope_keys]


def resolve_item_paths(
    root: Path,
    catalog: ScopeCatalog,
    scope_keys: Iterable[str],
    *,
    for_fingerprint: bool,
) -> list[str]:
    files: set[str] = set()
    for scope in item_scope_definitions(catalog, scope_keys):
        files.update(
            scope_paths(
                root,
                catalog,
                scope,
                include_shared=True,
                for_fingerprint=for_fingerprint,
            )
        )
    return sorted(files)
