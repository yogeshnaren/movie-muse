"""Committed provider recordings that feed DeterministicDoubleAdapter-compatible payloads.

Never opens a network connection. Never marks EXT-REMOTE-MODEL.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from movie_muse.model_router.api import AdapterResult
from movie_muse.testkit.errors import RecordingError
from movie_muse.testkit.paths import recordings_root


def load_recording(name: str, *, root: Path | None = None) -> dict[str, Any]:
    path = recordings_root(root) / f"{name}.json"
    if not path.is_file():
        raise RecordingError(f"missing provider recording {name}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RecordingError(f"recording {name} must be a JSON object")
    if payload.get("live") is True or payload.get("network") is True:
        raise RecordingError(f"recording {name} is marked live/network; doubles cannot call providers")
    required = ("capability", "output", "model_version", "method", "assumptions", "uncertainty")
    missing = [key for key in required if key not in payload]
    if missing:
        raise RecordingError(f"recording {name} missing fields: {missing}")
    return payload


def recording_to_adapter_result(payload: dict[str, Any]) -> AdapterResult:
    output = payload["output"]
    if not isinstance(output, dict):
        raise RecordingError("recording output must be an object")
    assumptions = tuple(str(item) for item in payload.get("assumptions") or ())
    return AdapterResult(
        output=dict(output),
        model_version=str(payload["model_version"]),
        input_tokens=int(payload.get("input_tokens") or 0),
        output_tokens=int(payload.get("output_tokens") or 0),
        actual_cost=float(payload.get("actual_cost") or 0.0),
        method=str(payload["method"]),
        assumptions=assumptions,
        uncertainty=str(payload["uncertainty"]),
    )


def load_adapter_result(name: str, *, root: Path | None = None) -> AdapterResult:
    return recording_to_adapter_result(load_recording(name, root=root))


def list_recordings(*, root: Path | None = None) -> tuple[str, ...]:
    directory = recordings_root(root)
    if not directory.is_dir():
        return ()
    return tuple(sorted(path.stem for path in directory.glob("*.json")))
