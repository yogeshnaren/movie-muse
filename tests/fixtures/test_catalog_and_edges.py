"""License, catalog, production-edge, and AST golden tests for MM-012."""

from __future__ import annotations

from pathlib import Path

from movie_muse.document.api import normalize
from movie_muse.schemas.api import BlockKind
from movie_muse.testkit.api import (
    REQUIRED_PRODUCTION_EDGES,
    FixtureCatalog,
    FixtureClass,
    NondeterminismGuard,
    load_rights_fixture,
)


def test_every_fixture_records_license_and_consent() -> None:
    catalog = FixtureCatalog()
    assert catalog.fixtures()
    for fixture in catalog.fixtures():
        lowered = fixture.license_text.lower()
        assert "license" in lowered
        assert "consent" in lowered
        assert fixture.rights.consent
        assert fixture.rights.license
        assert fixture.rights.origin
        assert fixture.rights.allow_training is False
        assert (Path(fixture.directory) / "rights.yaml").is_file()
        assert (Path(fixture.directory) / fixture.manifest.license_file).is_file()


def test_catalog_lists_all_four_classes() -> None:
    catalog = FixtureCatalog()
    assert catalog.classes() == frozenset(FixtureClass)


def test_required_production_edges_are_covered() -> None:
    catalog = FixtureCatalog()
    missing = catalog.missing_required_edges()
    assert missing == frozenset(), f"uncovered production-script edges: {sorted(missing)}"
    assert REQUIRED_PRODUCTION_EDGES <= catalog.covered_edges()


def test_unknown_extensions_are_preserved() -> None:
    catalog = FixtureCatalog()
    adversarial = catalog.get("adversarial_unicode_rtl")
    heading = next(
        block for block in adversarial.document.blocks if block.kind is BlockKind.SCENE_HEADING
    )
    assert "fdx_unknown_safe" in heading.unknown_extensions
    assert heading.unknown_extensions["fdx_unknown_safe"]["preserve"] is True


def test_rtl_and_unicode_survive_normalization() -> None:
    catalog = FixtureCatalog()
    adversarial = catalog.get("adversarial_unicode_rtl")
    arabic = next(
        block
        for block in adversarial.document.blocks
        if "مرحبا" in block.text
    )
    hebrew = next(
        block
        for block in adversarial.document.blocks
        if "שלום" in block.text
    )
    assert arabic.unknown_extensions["rtl"] is True
    assert "שלום" in hebrew.text
    assert "é" in adversarial.document.title or "cafe" in adversarial.document.title.lower()
    again = normalize(adversarial.document)
    assert again.title == adversarial.document.title


def test_live_ast_matches_committed_golden() -> None:
    catalog = FixtureCatalog()
    for fixture in catalog.fixtures():
        catalog.assert_ast_matches_golden(fixture.manifest.id)


def test_repeated_ast_hash_is_stable() -> None:
    catalog = FixtureCatalog()
    guard = NondeterminismGuard()
    for fixture in catalog.fixtures():
        digest = guard.assert_stable(
            lambda fixture_id=fixture.manifest.id: catalog.live_ast(fixture_id),
            times=5,
            label=f"ast:{fixture.manifest.id}",
        )
        assert digest == catalog.assert_ast_matches_golden(fixture.manifest.id)


def test_rights_fixtures_record_licensed_and_unlicensed() -> None:
    licensed = load_rights_fixture("licensed")
    unlicensed = load_rights_fixture("unlicensed")
    assert licensed["classification"] == "licensed"
    assert licensed["consent"]
    assert licensed["allow_training"] is False
    assert unlicensed["classification"] == "unlicensed"
    assert unlicensed["permitted_uses"] == []
