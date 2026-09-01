"""Profile coverage, fail-closed skips, and parse errors."""

from __future__ import annotations

import pytest

from movie_muse.fdx.api import FdxParseError, FdxService
from movie_muse.fdx.types import KIND_TO_PARAGRAPH
from movie_muse.schemas.api import BlockKind
from movie_muse.toolchain.paths import repo_root


def test_every_block_kind_has_a_paragraph_type() -> None:
    assert set(KIND_TO_PARAGRAPH) == set(BlockKind)


def test_malformed_xml_is_a_typed_parse_error() -> None:
    with pytest.raises(FdxParseError):
        FdxService().import_bytes(b"<FinalDraft><Content>")


def test_fdx_tests_do_not_skip_required_checks() -> None:
    package = repo_root() / "tests" / "fdx"
    skip_token = "pytest." + "skip("
    xfail_token = "pytest." + "xfail("
    for path in package.glob("test_*.py"):
        text = path.read_text(encoding="utf-8")
        assert skip_token not in text
        assert xfail_token not in text


def test_layout_module_is_not_faked_here() -> None:
    """Pagination hashes belong to MM-014. FDX must not skip or invent them."""

    assert not (repo_root() / "src" / "movie_muse" / "layout").exists()
    package = repo_root() / "src" / "movie_muse" / "fdx"
    joined = "\n".join(path.read_text(encoding="utf-8") for path in package.glob("*.py"))
    assert ("pytest." + "skip(") not in joined
