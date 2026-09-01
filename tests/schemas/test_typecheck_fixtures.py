"""Static half of the "cannot be silently promoted/interchanged" proof.

These fixture files under ``typecheck_fixtures/`` are deliberately outside
``[tool.mypy] packages = ["movie_muse"]`` so they never affect the main
``python3 -m mypy`` gate; this test explicitly invokes mypy on each one and
asserts the expected pass/fail outcome.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).resolve().parent / "typecheck_fixtures"


def _run_mypy(fixture_name: str) -> subprocess.CompletedProcess[str]:
    path = FIXTURES_DIR / fixture_name
    return subprocess.run(
        [sys.executable, "-m", "mypy", "--hide-error-context", str(path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize(
    "fixture_name",
    ["valid_epistemic_usage.py", "valid_stable_id_usage.py"],
)
def test_valid_fixture_type_checks_cleanly(fixture_name: str) -> None:
    result = _run_mypy(fixture_name)
    assert result.returncode == 0, result.stdout + result.stderr


def test_invalid_epistemic_promotion_is_a_type_error() -> None:
    result = _run_mypy("invalid_epistemic_promotion.py")
    assert result.returncode != 0
    assert "StructuralFact" in result.stdout
    assert "AuthoredFact" in result.stdout
    assert "incompatible type" in result.stdout


def test_invalid_stable_id_mismatch_is_a_type_error() -> None:
    result = _run_mypy("invalid_stable_id_mismatch.py")
    assert result.returncode != 0
    assert "NoteId" in result.stdout
    assert "SceneId" in result.stdout
    assert "incompatible type" in result.stdout
