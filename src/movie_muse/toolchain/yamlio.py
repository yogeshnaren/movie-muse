"""YAML helpers. Round-trip the status manifest; safe-load configuration files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from ruamel.yaml import YAML


def load_mapping(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must contain a mapping")
    return loaded


def load_round_trip(path: Path) -> Any:
    yaml_rt = YAML()
    yaml_rt.preserve_quotes = True
    with path.open(encoding="utf-8") as handle:
        return yaml_rt.load(handle)


def dump_round_trip(path: Path, data: Any) -> None:
    yaml_rt = YAML()
    yaml_rt.preserve_quotes = True
    yaml_rt.width = 120
    with path.open("w", encoding="utf-8") as handle:
        yaml_rt.dump(data, handle)
