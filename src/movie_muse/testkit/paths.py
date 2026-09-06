"""Repository and fixture-tree locations."""

from __future__ import annotations

from pathlib import Path

from movie_muse.toolchain import repo_root


def fixtures_root(root: Path | None = None) -> Path:
    return (root or repo_root()) / "fixtures"


def screenplay_fixtures_root(root: Path | None = None) -> Path:
    return fixtures_root(root) / "screenplays"


def recordings_root(root: Path | None = None) -> Path:
    return fixtures_root(root) / "recordings"


def rights_fixtures_root(root: Path | None = None) -> Path:
    return fixtures_root(root) / "rights"


def bench_root(root: Path | None = None) -> Path:
    return fixtures_root(root) / "bench"


def golden_path_root(root: Path | None = None) -> Path:
    return fixtures_root(root) / "golden_path"
