from __future__ import annotations

from pathlib import Path

import pytest

from movie_muse.toolchain.paths import repo_root
from movie_muse.toolchain.secrets import PATTERNS, SecretHit, scan_secrets


@pytest.mark.security
def test_repository_has_no_live_secrets() -> None:
    hits = scan_secrets(repo_root())
    assert hits == []


@pytest.mark.security
def test_placeholder_env_example_is_not_flagged() -> None:
    root = repo_root()
    text = (root / ".env.example").read_text(encoding="utf-8")
    assert "YOUR_KEY_HERE" in text
    assert "AKIA" not in text


@pytest.mark.security
def test_scanner_detects_aws_key(tmp_path: Path) -> None:
    sample = 'key = "AKIAIOSFODNN7EXAMPLE"'
    matches = [kind for kind, pattern in PATTERNS if pattern.search(sample)]
    assert "aws_access_key" in matches


@pytest.mark.security
def test_secret_hit_dataclass() -> None:
    hit = SecretHit(path="x.py", line=3, kind="aws_access_key")
    assert hit.kind == "aws_access_key"
