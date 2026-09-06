"""Expected-artifact availability. Fail closed; never pytest.skip required checks."""

from __future__ import annotations

from typing import Any

from movie_muse.testkit.errors import ExpectedArtifactError
from movie_muse.testkit.types import (
    DEFERRED_AWAITING,
    KNOWN_PRODUCERS,
    REQUIRED_CURRENT_KINDS,
    ExpectedArtifact,
    ExpectedKind,
    ExpectedStatus,
)


def parse_expected(data: dict[str, Any]) -> ExpectedArtifact:
    return ExpectedArtifact.from_dict(data)


def deferred_placeholder(kind: ExpectedKind) -> ExpectedArtifact:
    awaiting = DEFERRED_AWAITING[kind]
    return ExpectedArtifact(
        kind=kind,
        status=ExpectedStatus.DEFERRED,
        producer=None,
        awaiting=awaiting,
        payload=None,
        note=(
            f"No honest {kind.value} producer exists yet. Awaiting {awaiting}. "
            "This record is not compared as if a compiler ran."
        ),
    )


def assert_expected_available(record: ExpectedArtifact) -> ExpectedArtifact:
    """Return the record after enforcing fail-closed producer rules.

    AST goldens are required and must be current with a known producer.
    Layout/FilmIR may be deferred and disclosed. Marking them current without
    a known producer fails closed. Callers must not pytest.skip this check.
    """

    if record.status is ExpectedStatus.CURRENT:
        if record.producer not in KNOWN_PRODUCERS:
            raise ExpectedArtifactError(
                f"{record.kind.value} is marked current without a known producer"
            )
        if record.payload is None:
            raise ExpectedArtifactError(f"{record.kind.value} current golden is missing payload")
        return record
    if record.kind in REQUIRED_CURRENT_KINDS:
        raise ExpectedArtifactError(
            f"{record.kind.value} golden is required for MM-012 and cannot be deferred"
        )
    expected_awaiting = DEFERRED_AWAITING.get(record.kind)
    if expected_awaiting and record.awaiting != expected_awaiting:
        raise ExpectedArtifactError(
            f"{record.kind.value} deferred record must await {expected_awaiting}"
        )
    return record
