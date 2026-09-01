"""Golden registry, expected-artifact, and nondeterminism harness tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from movie_muse.testkit.api import (
    REVIEW_TOKEN_PLACEHOLDER,
    ExpectedArtifact,
    ExpectedArtifactError,
    ExpectedKind,
    ExpectedStatus,
    FixtureCatalog,
    GoldenRegistry,
    NondeterminismError,
    NondeterminismGuard,
    UnapprovedGoldenUpdateError,
    approve_golden_update,
    assert_expected_available,
)


def test_unapproved_golden_overwrite_is_denied(tmp_path: Path) -> None:
    catalog = FixtureCatalog()
    fixture = catalog.get("small_kitchen")
    target = tmp_path / "small_kitchen"
    expected_dir = target / "expected"
    expected_dir.mkdir(parents=True)
    original = json.loads(
        (Path(fixture.directory) / "expected" / "ast.json").read_text(encoding="utf-8")
    )
    (expected_dir / "ast.json").write_text(
        json.dumps(original, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    registry = GoldenRegistry(target)
    mutated = dict(original)
    mutated["note"] = "tampered"
    with pytest.raises(UnapprovedGoldenUpdateError, match="approve_golden_update"):
        registry.write(ExpectedKind.AST, mutated)
    approval = approve_golden_update(
        fixture_id="small_kitchen",
        kind=ExpectedKind.AST,
        payload=mutated,
        token=REVIEW_TOKEN_PLACEHOLDER,
    )
    registry.write(ExpectedKind.AST, mutated, approval=approval)
    loaded = registry.load(ExpectedKind.AST)
    assert loaded["note"] == "tampered"


def test_layout_and_film_ir_are_deferred_not_skipped() -> None:
    catalog = FixtureCatalog()
    for fixture in catalog.fixtures():
        layout = catalog.assert_expected_available(fixture.manifest.id, ExpectedKind.LAYOUT)
        film_ir = catalog.assert_expected_available(fixture.manifest.id, ExpectedKind.FILM_IR)
        assert layout.status is ExpectedStatus.DEFERRED
        assert layout.awaiting == "MM-014"
        assert layout.producer is None
        assert film_ir.status is ExpectedStatus.DEFERRED
        assert film_ir.awaiting == "MM-018"
        assert film_ir.producer is None


def test_current_without_producer_fails_closed() -> None:
    bogus = ExpectedArtifact(
        kind=ExpectedKind.LAYOUT,
        status=ExpectedStatus.CURRENT,
        producer=None,
        awaiting=None,
        payload={"pretend": True},
    )
    with pytest.raises(ExpectedArtifactError, match="without a known producer"):
        assert_expected_available(bogus)
    required_deferred = ExpectedArtifact(
        kind=ExpectedKind.AST,
        status=ExpectedStatus.DEFERRED,
        producer=None,
        awaiting="MM-014",
        payload=None,
    )
    with pytest.raises(ExpectedArtifactError, match="cannot be deferred"):
        assert_expected_available(required_deferred)


def test_nondeterminism_guard_detects_mismatch() -> None:
    guard = NondeterminismGuard()
    values = iter(({"n": 1}, {"n": 2}))
    with pytest.raises(NondeterminismError):
        guard.assert_stable(lambda: next(values), times=2, label="jitter")
