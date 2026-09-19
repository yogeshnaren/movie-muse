"""Fail-closed editor errors."""

from __future__ import annotations


class EditorError(RuntimeError):
    """Base class for editor session failures."""


class EditorCanonError(EditorError):
    """A caller tried to persist editor JSON as ScreenplayDocument canon."""


class EditorCommandError(EditorError):
    """A keystroke or menu command could not be translated to a ChangeSet."""


class RecoveryError(EditorError):
    """The recovery journal could not be replayed safely."""
