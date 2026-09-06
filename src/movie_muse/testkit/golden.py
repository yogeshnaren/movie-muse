"""Golden file registry. Overwrites require an explicit reviewed approval."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from movie_muse.persistence.api import digest_payload
from movie_muse.testkit.errors import TestkitError, UnapprovedGoldenUpdateError
from movie_muse.testkit.types import ExpectedKind, GoldenApproval

REVIEW_TOKEN_PLACEHOLDER = "replace-me-golden-review"


def _canonical(payload: dict[str, Any]) -> bytes:
    encoded, _digest = digest_payload(payload)
    return encoded


def payload_digest(payload: dict[str, Any]) -> str:
    _encoded, digest = digest_payload(payload)
    return digest


def sign_golden_update(
    *,
    token: str,
    fixture_id: str,
    kind: ExpectedKind | str,
    digest: str,
) -> str:
    kind_value = kind.value if isinstance(kind, ExpectedKind) else str(kind)
    material = f"{token}\n{fixture_id}\n{kind_value}\n{digest}".encode()
    return hashlib.sha256(material).hexdigest()


def approve_golden_update(
    *,
    fixture_id: str,
    kind: ExpectedKind | str,
    payload: dict[str, Any],
    token: str,
) -> GoldenApproval:
    parsed = kind if isinstance(kind, ExpectedKind) else ExpectedKind(str(kind))
    digest = payload_digest(payload)
    signature = sign_golden_update(
        token=token, fixture_id=fixture_id, kind=parsed, digest=digest
    )
    return GoldenApproval(
        fixture_id=fixture_id,
        kind=parsed,
        payload_digest=digest,
        token=token,
        signature=signature,
    )


class GoldenRegistry:
    """File-backed expected artifacts. Mutation without approval fails closed."""

    def __init__(self, fixture_dir: Path) -> None:
        self.fixture_dir = Path(fixture_dir)
        self.expected_dir = self.fixture_dir / "expected"

    def path_for(self, kind: ExpectedKind | str) -> Path:
        parsed = kind if isinstance(kind, ExpectedKind) else ExpectedKind(str(kind))
        return self.expected_dir / f"{parsed.value}.json"

    def load(self, kind: ExpectedKind | str) -> dict[str, Any]:
        path = self.path_for(kind)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TestkitError(f"{path} must contain a JSON object")
        return payload

    def write(
        self,
        kind: ExpectedKind | str,
        payload: dict[str, Any],
        *,
        approval: GoldenApproval | None = None,
    ) -> Path:
        path = self.path_for(kind)
        parsed = kind if isinstance(kind, ExpectedKind) else ExpectedKind(str(kind))
        if path.exists():
            self._require_approval(parsed, payload, approval)
        self.expected_dir.mkdir(parents=True, exist_ok=True)
        pretty = json.dumps(
            json.loads(_canonical(payload).decode("utf-8")),
            indent=2,
            ensure_ascii=False,
        )
        path.write_text(pretty + "\n", encoding="utf-8")
        return path

    def _require_approval(
        self,
        kind: ExpectedKind,
        payload: dict[str, Any],
        approval: GoldenApproval | None,
    ) -> None:
        if approval is None:
            raise UnapprovedGoldenUpdateError(
                f"golden {self.fixture_dir.name}/{kind.value} overwrite requires approve_golden_update"
            )
        expected = approve_golden_update(
            fixture_id=approval.fixture_id,
            kind=kind,
            payload=payload,
            token=approval.token,
        )
        if (
            approval.fixture_id != self.fixture_dir.name
            or approval.kind is not kind
            or approval.payload_digest != expected.payload_digest
            or approval.signature != expected.signature
        ):
            raise UnapprovedGoldenUpdateError(
                f"golden {self.fixture_dir.name}/{kind.value} approval does not match payload"
            )
