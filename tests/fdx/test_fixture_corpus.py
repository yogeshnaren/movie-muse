"""Committed FDX fixtures are legally original and round-trip through the profile."""

from __future__ import annotations

from pathlib import Path

import yaml

from movie_muse.fdx.api import FdxService
from movie_muse.toolchain.paths import repo_root


def _fdx_root() -> Path:
    return repo_root() / "fixtures" / "fdx"


def test_fdx_fixtures_record_license_and_non_competitor_origin() -> None:
    root = _fdx_root()
    license_text = (root / "LICENSE.md").read_text(encoding="utf-8")
    assert "CC0" in license_text
    assert "Not copied from Final Draft" in license_text
    rights = yaml.safe_load((root / "rights.yaml").read_text(encoding="utf-8"))
    assert rights["allow_training"] is False
    assert rights["copied_from_final_draft"] is False
    manifest = yaml.safe_load((root / "MANIFEST.yaml").read_text(encoding="utf-8"))
    assert manifest["copied_from_final_draft"] is False
    files = {entry["path"] for entry in manifest["files"]}
    assert files == {path.name for path in root.glob("*.fdx")}


def test_committed_fdx_files_import_and_reexport_deterministically() -> None:
    service = FdxService()
    root = _fdx_root()
    for path in sorted(root.glob("*.fdx")):
        document, report = service.import_path(path)
        assert document.blocks
        exported = service.export_document(document)
        imported, second = service.import_bytes(exported)
        service.assert_lossless(document, imported)
        assert exported == service.export_document(imported)
        if path.name == "unknown_extension.fdx":
            assert not report.lossless
            codes = {item.code for item in report.items}
            assert "unsupported_paragraph_type" in codes
            assert "unknown_child_preserved" in codes
            assert "unknown_attribute_preserved" in codes
            assert second.lossless
        else:
            assert report.lossless, (path.name, report.to_dict())


def test_title_page_only_foreign_fdx_is_imported() -> None:
    service = FdxService()
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<FinalDraft DocumentType="Script" Version="1">
  <Content/>
  <TitlePage>
    <Paragraph Type="Title"><Text>THE KEY</Text></Paragraph>
  </TitlePage>
</FinalDraft>
"""
    document, report = service.import_bytes(xml.encode("utf-8"))
    assert not report.lossless
    assert document.blocks
    assert document.blocks[0].kind.value == "title_page_element"
    assert document.blocks[0].text == "THE KEY"
