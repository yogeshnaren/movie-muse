"""Declared regression thresholds for the state-engine corpus."""

from __future__ import annotations

from typing import Final

DECLARED_THRESHOLDS: Final[dict[str, float]] = {
    "temporal_query_agreement": 1.0,
    "contradiction_with_evidence": 1.0,
    "correction_overrides_inferred": 1.0,
    "second_order_belief_recovery": 1.0,
    "determinism": 1.0,
}
