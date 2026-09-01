"""Fail-closed source secret scanner. Placeholders are allowed; live credentials are not."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from movie_muse.toolchain.scopes import SKIP_DIR_NAMES, matches_any
from movie_muse.toolchain.yamlio import load_mapping

PLACEHOLDERS = ("CHANGE_ME", "YOUR_KEY_HERE", "replace-me", "sk-test-not-a-real-key", "example")

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("pem_private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("github_pat", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("openai_live_key", re.compile(r"sk-live-[A-Za-z0-9]{10,}")),
    ("anthropic_live_key", re.compile(r"sk-ant-[A-Za-z0-9-]{10,}")),
    ("generic_password_assignment", re.compile(r"(?i)(password|secret)\s*=\s*['\"][^'\"]{12,}['\"]")),
)


@dataclass(frozen=True)
class SecretHit:
    path: str
    line: int
    kind: str


def _is_placeholder(text: str) -> bool:
    lowered = text.lower()
    return any(token.lower() in lowered for token in PLACEHOLDERS)


def iter_source_files(root: Path, exclude_globs: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in SKIP_DIR_NAMES for part in rel_parts):
            continue
        rel = path.relative_to(root).as_posix()
        if matches_any(rel, exclude_globs):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".pyc"}:
            continue
        files.append(path)
    return files


def scan_secrets(root: Path) -> list[SecretHit]:
    policy = load_mapping(root / "config" / "secrets-policy.yaml")
    exclude = [str(item) for item in (policy.get("exclude_globs") or [])]
    hits: list[SecretHit] = []
    for path in iter_source_files(root, exclude):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for index, line in enumerate(text.splitlines(), start=1):
            if _is_placeholder(line):
                continue
            for kind, pattern in PATTERNS:
                if pattern.search(line):
                    hits.append(
                        SecretHit(
                            path=path.relative_to(root).as_posix(),
                            line=index,
                            kind=kind,
                        )
                    )
    return hits
