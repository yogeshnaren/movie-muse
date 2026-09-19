"""Public surface of ``movie_muse.compiler``.

Hosts and other modules must import this module, never sibling internals.
The compiler is deterministic and does not call ModelRouter.
"""

from __future__ import annotations

from movie_muse.compiler.errors import CompilerError, CompileValidationError
from movie_muse.compiler.service import CompilerService
from movie_muse.compiler.syntax import normalize_character_name, parse_scene_heading
from movie_muse.compiler.types import (
    COMPILER_VERSION,
    CompiledEntity,
    CompiledScene,
    CompiledScreenplay,
)

__all__ = [
    "COMPILER_VERSION",
    "CompiledEntity",
    "CompiledScene",
    "CompiledScreenplay",
    "CompileValidationError",
    "CompilerError",
    "CompilerService",
    "normalize_character_name",
    "parse_scene_heading",
]
