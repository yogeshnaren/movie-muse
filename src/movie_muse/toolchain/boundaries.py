"""Module-boundary import scanner. Cross-module internals are forbidden."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from movie_muse.toolchain.yamlio import load_mapping

INTERNAL_MARKERS = ("internal", "_internal", "tables", "models", "repository")


@dataclass(frozen=True)
class BoundaryViolation:
    path: str
    line: int
    statement: str
    reason: str


def _package_parts(module: str) -> list[str]:
    return [part for part in module.split(".") if part]


def _is_internal_import(imported: str, current_module: str) -> bool:
    imported_parts = _package_parts(imported)
    current_parts = _package_parts(current_module)
    if len(imported_parts) < 3 or imported_parts[0] != "movie_muse":
        return False
    if imported_parts[1] == "toolchain":
        return False
    if len(current_parts) >= 2 and imported_parts[1] == current_parts[1]:
        return False
    if imported_parts[-1] == "api":
        return False
    if any(marker in imported_parts[2:] for marker in INTERNAL_MARKERS):
        return True
    return len(imported_parts) > 2 and imported_parts[-1] != "api"


def module_name_for_path(root: Path, path: Path) -> str:
    resolved = path.resolve()
    src_root = (root / "src").resolve()
    try:
        rel = resolved.relative_to(src_root)
    except ValueError:
        rel = resolved.relative_to(root.resolve())
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def scan_file(root: Path, path: Path) -> list[BoundaryViolation]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    current = module_name_for_path(root, path)
    violations: list[BoundaryViolation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported = node.module
            if _is_internal_import(imported, current):
                violations.append(
                    BoundaryViolation(
                        path=str(path.relative_to(root).as_posix()),
                        line=node.lineno,
                        statement=imported,
                        reason="cross-module internal import",
                    )
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _is_internal_import(alias.name, current):
                    violations.append(
                        BoundaryViolation(
                            path=str(path.relative_to(root).as_posix()),
                            line=node.lineno,
                            statement=alias.name,
                            reason="cross-module internal import",
                        )
                    )
    return violations


def iter_python_files(root: Path, scan_roots: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for rel in scan_roots:
        base = root / rel
        if base.is_file() and base.suffix == ".py":
            files.append(base)
            continue
        if not base.exists():
            continue
        files.extend(sorted(path for path in base.rglob("*.py") if path.is_file()))
    return files


def scan_boundaries(root: Path) -> list[BoundaryViolation]:
    layout = load_mapping(root / "config" / "module-layout.yaml")
    scan_roots = [str(layout.get("source_root", "src/movie_muse"))]
    scan_roots.extend(str(host) for host in (layout.get("application_hosts") or []))
    violations: list[BoundaryViolation] = []
    for path in iter_python_files(root, scan_roots):
        if "tests" in path.parts:
            continue
        violations.extend(scan_file(root, path))
    return violations
