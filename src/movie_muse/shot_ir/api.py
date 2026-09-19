"""Public surface of ``movie_muse.shot_ir``.

Hosts and other modules must import this module, never sibling internals.
ShotIR is model/provider independent. Diagrammatic shot cards work with
generation disabled.
"""

from __future__ import annotations

from movie_muse.schemas.api import CameraSpec, ShotIR
from movie_muse.shot_ir.errors import (
    LockedAttributeError,
    ProviderIndependentError,
    ShotIRError,
    ShotNotFoundError,
)
from movie_muse.shot_ir.service import CAMERA_FIELDS, ShotIRService
from movie_muse.shot_ir.types import ShotCard, StoredShot

__all__ = [
    "CAMERA_FIELDS",
    "CameraSpec",
    "LockedAttributeError",
    "ProviderIndependentError",
    "ShotCard",
    "ShotIR",
    "ShotIRError",
    "ShotIRService",
    "ShotNotFoundError",
    "StoredShot",
]
