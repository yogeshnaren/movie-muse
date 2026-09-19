"""Declared completeness and accuracy thresholds for production breakdown."""

from __future__ import annotations

from typing import Final

DECLARED_THRESHOLDS: Final[dict[str, float]] = {
    "completeness": 1.0,
    "accuracy": 1.0,
    "evidence_link_rate": 1.0,
}
