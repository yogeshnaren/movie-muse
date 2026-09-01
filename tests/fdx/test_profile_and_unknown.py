"""Profile validation, unknown-safe preservation, and explicit disclosures."""

from __future__ import annotations

import pytest

from movie_muse.fdx.api import PROFILE_NAME, FdxProfileError, FdxService


def test_profile_rejects_non_finaldraft_root() -> None:
    service = FdxService()
    with pytest.raises(FdxProfileError):
        service.validate(b"<NotDraft><Content/></NotDraft>")


def test_unknown_paragraph_type_is_preserved_and_disclosed() -> None:
    service = FdxService()
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<FinalDraft DocumentType="Script" Template="MovieMuse" Version="1" xmlns:mm="https://movie-muse.dev/fdx">
  <Content>
    <Paragraph Type="Scene Heading" mm:block-id="blk_01J6NE390B000000000000000B" mm:scene-id="scn_01J6NE39060000000000000006" Number="1">
      <Text>INT. ROOM - DAY</Text>
    </Paragraph>
    <Paragraph Type="Cast List">
      <Text>ADA</Text>
    </Paragraph>
  </Content>
</FinalDraft>
"""
    document, report = service.import_bytes(xml.encode("utf-8"))
    assert not report.lossless
    assert any(item.code == "unsupported_paragraph_type" for item in report.items)
    preserved = [block for block in document.blocks if block.unknown_extensions.get("_fdx_paragraph_type") == "Cast List"]
    assert preserved
    assert preserved[0].text == "ADA"


def test_unknown_child_element_is_disclosed() -> None:
    service = FdxService()
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<FinalDraft DocumentType="Script" Template="MovieMuse" Version="1" xmlns:mm="https://movie-muse.dev/fdx">
  <Content>
    <Paragraph Type="Action" mm:block-id="blk_01J6NE390C000000000000000C">
      <Text>Ada waits.</Text>
      <CustomMarkup Foo="bar">kept</CustomMarkup>
    </Paragraph>
  </Content>
</FinalDraft>
"""
    document, report = service.import_bytes(xml.encode("utf-8"))
    assert any(item.code == "unknown_child_preserved" for item in report.items)
    extras = document.blocks[0].unknown_extensions.get("_fdx_extra_elements")
    assert extras
    assert extras[0]["tag"] == "CustomMarkup"


def test_profile_name_is_movie_muse() -> None:
    assert PROFILE_NAME == "movie_muse_fdx"
