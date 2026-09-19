#!/usr/bin/env python3
"""Fail-closed completion preflight for verify_all.

Build-plan §7 requires clean/reproducible prerequisites, pinned tools,
current PASS fingerprints, and evidence files generated from the tested
commit. This script does not print the product sentinel. Live/sandbox
absence is still owned by _live_probes.py.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from movie_muse.toolchain.engine import (
    fingerprint_item,
    git_is_clean,
    items_by_id,
    load_workspace,
)
from movie_muse.toolchain.paths import repo_root

PINNED_PACKAGES = (
    ("ruff", "0.12.12"),
    ("mypy", "1.17.1"),
    ("pytest", "8.4.1"),
    ("jsonschema", "4.26.0"),
    ("ruamel.yaml", "0.18.10"),
)
NODE_MAJOR_ALLOWED = frozenset({20, 21, 22})


def _pinned_tool_problems() -> list[str]:
    problems: list[str] = []
    for name, expected in PINNED_PACKAGES:
        try:
            found = metadata.version(name)
        except metadata.PackageNotFoundError:
            problems.append(f"missing_tool:{name}")
            continue
        if found != expected:
            problems.append(f"unpinned_tool:{name}={found}!={expected}")
    node = shutil.which("node")
    if node is None:
        problems.append("missing_tool:node")
        return problems
    try:
        output = subprocess.check_output([node, "-v"], text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        problems.append(f"node_version_unreadable:{exc}")
        return problems
    digits = output.lstrip("v").split(".", 1)[0]
    if not digits.isdigit() or int(digits) not in NODE_MAJOR_ALLOWED:
        problems.append(f"node_version={output}")
    return problems


def completion_problems(root: Path | None = None) -> list[str]:
    root = root or repo_root()
    problems: list[str] = []
    if not git_is_clean(root):
        problems.append("dirty_worktree")
    version = sys.version_info
    if version < (3, 11) or version >= (3, 13):
        problems.append(f"python_version={version.major}.{version.minor}")
    problems.extend(_pinned_tool_problems())
    manifest, _dag, catalog = load_workspace(root)
    items = items_by_id(manifest)
    for item_id, item in items.items():
        if item.get("status") != "PASS":
            continue
        record = item.get("pass_record") or {}
        commit = str(record.get("verification_commit") or "")
        digest = str(record.get("input_fingerprint") or "")
        if not commit or not digest:
            problems.append(f"incomplete_pass_record:{item_id}")
            continue
        computed = fingerprint_item(
            root,
            manifest,
            catalog,
            item_id,
            verification_commit=commit,
        )
        if computed["input_fingerprint"] != digest:
            problems.append(f"stale_fingerprint:{item_id}")
        for evidence in record.get("evidence") or []:
            path = root / str(evidence)
            if not path.exists():
                problems.append(f"missing_evidence:{item_id}:{evidence}")
    return problems


def main() -> int:
    problems = completion_problems()
    if problems:
        print(
            "MOVIE_MUSE_PROTOTYPE_VERIFICATION=NOT_READY completion_preflight="
            + ",".join(problems),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
