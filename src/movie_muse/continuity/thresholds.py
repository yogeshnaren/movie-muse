"""Declared recall and false-positive budget for continuity analysis."""

from __future__ import annotations

from typing import Final

DECLARED_THRESHOLDS: Final[dict[str, float]] = {
    "high_severity_recall": 1.0,
    "false_positive_rate": 0.0,
    "determinism": 1.0,
}
