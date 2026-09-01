"""Repository root discovery for Movie Muse toolchain commands."""

from __future__ import annotations

from pathlib import Path

_MARKERS = ("movie_muse_build_status.yaml", "dependency_dag.yaml", "pyproject.toml")


def repo_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if all((candidate / marker).is_file() for marker in _MARKERS):
            return candidate
    raise FileNotFoundError("unable to locate Movie Muse repository root")
