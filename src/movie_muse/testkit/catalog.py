"""Fixture catalog over committed screenplay, rights, and expected artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from movie_muse.document.api import normalize, semantic_validate
from movie_muse.schemas.api import ScreenplayDocument, validate_payload
from movie_muse.testkit.ast import dump_ast
from movie_muse.testkit.errors import (
    ExpectedArtifactError,
    FixtureLicenseError,
    FixtureNotFoundError,
)
from movie_muse.testkit.expected import assert_expected_available, parse_expected
from movie_muse.testkit.golden import GoldenRegistry, payload_digest
from movie_muse.testkit.paths import rights_fixtures_root, screenplay_fixtures_root
from movie_muse.testkit.types import (
    REQUIRED_PRODUCTION_EDGES,
    ExpectedArtifact,
    ExpectedKind,
    FixtureClass,
    FixtureManifest,
    FixtureRights,
    ScreenplayFixture,
)


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise FixtureLicenseError(f"{path} must contain a mapping")
    return loaded


def _manifest(directory: Path) -> FixtureManifest:
    raw = _load_yaml(directory / "MANIFEST.yaml")
    edges = tuple(str(item) for item in (raw.get("edges") or ()))
    return FixtureManifest(
        id=str(raw["id"]),
        fixture_class=FixtureClass(str(raw["class"])),
        title=str(raw["title"]),
        edges=edges,
        license_file=str(raw.get("license_file") or "LICENSE.md"),
        rights_file=str(raw.get("rights_file") or "rights.yaml"),
    )


def _rights(directory: Path, filename: str) -> FixtureRights:
    raw = _load_yaml(directory / filename)
    uses = tuple(str(item) for item in (raw.get("permitted_uses") or ()))
    return FixtureRights(
        classification=str(raw["classification"]),
        license=str(raw["license"]),
        consent=str(raw["consent"]),
        origin=str(raw["origin"]),
        allow_training=bool(raw.get("allow_training", False)),
        permitted_uses=uses,
    )


def _require_license(directory: Path, manifest: FixtureManifest, rights: FixtureRights) -> str:
    license_path = directory / manifest.license_file
    rights_path = directory / manifest.rights_file
    if not license_path.is_file():
        raise FixtureLicenseError(f"{manifest.id} is missing {manifest.license_file}")
    if not rights_path.is_file():
        raise FixtureLicenseError(f"{manifest.id} is missing {manifest.rights_file}")
    text = license_path.read_text(encoding="utf-8")
    lowered = text.lower()
    if "license" not in lowered or "consent" not in lowered:
        raise FixtureLicenseError(f"{manifest.id} license file must record license and consent")
    if not rights.consent or not rights.license or not rights.origin:
        raise FixtureLicenseError(f"{manifest.id} rights.yaml must record license, consent, and origin")
    if rights.allow_training:
        raise FixtureLicenseError(
            f"{manifest.id} must not imply training consent; allow_training must stay false"
        )
    return text


def load_screenplay_document(directory: Path) -> ScreenplayDocument:
    payload = json.loads((directory / "document.json").read_text(encoding="utf-8"))
    validate_payload("screenplay_document", payload)
    document = ScreenplayDocument.from_dict(payload)
    normalized = normalize(document)
    semantic_validate(normalized)
    return normalized


class FixtureCatalog:
    def __init__(self, root: Path | None = None) -> None:
        self.root = screenplay_fixtures_root(root)
        self._fixtures = self._discover()

    def _discover(self) -> dict[str, ScreenplayFixture]:
        found: dict[str, ScreenplayFixture] = {}
        if not self.root.is_dir():
            return found
        for directory in sorted(path for path in self.root.iterdir() if path.is_dir()):
            if not (directory / "MANIFEST.yaml").is_file():
                continue
            manifest = _manifest(directory)
            rights = _rights(directory, manifest.rights_file)
            license_text = _require_license(directory, manifest, rights)
            document = load_screenplay_document(directory)
            found[manifest.id] = ScreenplayFixture(
                manifest=manifest,
                document=document,
                rights=rights,
                license_text=license_text,
                directory=str(directory),
            )
        return found

    def fixtures(self) -> tuple[ScreenplayFixture, ...]:
        return tuple(self._fixtures[key] for key in sorted(self._fixtures))

    def get(self, fixture_id: str) -> ScreenplayFixture:
        try:
            return self._fixtures[fixture_id]
        except KeyError as exc:
            raise FixtureNotFoundError(fixture_id) from exc

    def classes(self) -> frozenset[FixtureClass]:
        return frozenset(item.manifest.fixture_class for item in self._fixtures.values())

    def covered_edges(self) -> frozenset[str]:
        edges: set[str] = set()
        for item in self._fixtures.values():
            edges.update(item.manifest.edges)
        return frozenset(edges)

    def missing_required_edges(self) -> frozenset[str]:
        return REQUIRED_PRODUCTION_EDGES - self.covered_edges()

    def golden_registry(self, fixture_id: str) -> GoldenRegistry:
        fixture = self.get(fixture_id)
        return GoldenRegistry(Path(fixture.directory))

    def expected(self, fixture_id: str, kind: ExpectedKind | str) -> ExpectedArtifact:
        parsed = kind if isinstance(kind, ExpectedKind) else ExpectedKind(str(kind))
        raw = self.golden_registry(fixture_id).load(parsed)
        return parse_expected(raw)

    def assert_expected_available(
        self, fixture_id: str, kind: ExpectedKind | str
    ) -> ExpectedArtifact:
        return assert_expected_available(self.expected(fixture_id, kind))

    def live_ast(self, fixture_id: str) -> dict[str, Any]:
        return dump_ast(self.get(fixture_id).document)

    def assert_ast_matches_golden(self, fixture_id: str) -> str:
        live = self.live_ast(fixture_id)
        raw = self.golden_registry(fixture_id).load(ExpectedKind.AST)
        self.assert_expected_available(fixture_id, ExpectedKind.AST)
        live_digest = payload_digest(live)
        golden_digest = payload_digest(raw)
        if live_digest != golden_digest:
            raise ExpectedArtifactError(
                f"{fixture_id} live AST digest {live_digest} != golden {golden_digest}"
            )
        return live_digest


def load_rights_fixture(name: str, *, root: Path | None = None) -> dict[str, Any]:
    path = rights_fixtures_root(root) / f"{name}.yaml"
    return _load_yaml(path)
