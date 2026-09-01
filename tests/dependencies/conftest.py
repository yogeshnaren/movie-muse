"""MM-011 pytest fixtures. Helpers are loaded by path to avoid conftest name clashes."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _helpers():
    name = "movie_muse_mm011_helpers"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    path = Path(__file__).with_name("helpers.py")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_helpers_mod = _helpers()
DependencyStack = _helpers_mod.DependencyStack
boot_dependency_stack = _helpers_mod.boot_dependency_stack


@pytest.fixture
def dep_stack(tmp_path: Path) -> DependencyStack:
    stack = boot_dependency_stack(tmp_path / "workspace")
    yield stack
    stack.workspace.close()
