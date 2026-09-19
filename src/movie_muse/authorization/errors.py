"""Fail-closed errors for the authorization module."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from movie_muse.authorization.types import Decision


class AuthorizationError(ValueError):
    """A command was denied by the local ACL authority."""

    def __init__(self, message: str, decision: Decision | None = None) -> None:
        super().__init__(message)
        self.decision = decision
