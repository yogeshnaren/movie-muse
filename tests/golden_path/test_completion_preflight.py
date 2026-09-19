"""Completion preflight is wired into the golden-path named gate."""

from __future__ import annotations

import importlib.util

from movie_muse.toolchain.paths import repo_root


def _load_preflight():
    path = repo_root() / "scripts" / "gates" / "_completion_preflight.py"
    spec = importlib.util.spec_from_file_location("mm047_completion_preflight", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_completion_preflight_is_wired_into_golden_path_gate() -> None:
    root = repo_root()
    script = root / "scripts" / "gates" / "golden_path_41_steps.sh"
    assert "_completion_preflight.py" in script.read_text(encoding="utf-8")
    assert (root / "scripts" / "gates" / "_completion_preflight.py").is_file()
    problems = _load_preflight().completion_problems()
    assert isinstance(problems, list)
