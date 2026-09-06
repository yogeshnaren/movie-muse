"""Role/device mode projections over one canonical project. Never fork state."""

from __future__ import annotations

from movie_muse.authorization.policy import compose_mode_actions, compose_visible_fields
from movie_muse.authorization.types import Action, ComposedMode, Mode, ProjectView
from movie_muse.identity.api import Principal
from movie_muse.persistence.api import LocalWorkspace


def compose_modes(modes: tuple[Mode, ...] | list[Mode]) -> ComposedMode:
    normalized = tuple(modes)
    return ComposedMode(modes=normalized, allowed_actions=compose_mode_actions(normalized))


def live_head_revision_id(workspace: LocalWorkspace, document_id: str | None = None) -> str:
    """Read the canonical head from the workspace. Modes must share this id."""

    doc_id = document_id or workspace.store.get_meta("active_document_id")
    if doc_id is None:
        return ""
    head = workspace.head_revision_id(doc_id)
    return head or ""


def project_view(
    mode: Mode | tuple[Mode, ...] | list[Mode],
    principal: Principal,
    *,
    project_id: str,
    organization_id: str,
    workspace: LocalWorkspace,
    granted_actions: frozenset[Action],
    document_id: str | None = None,
) -> ProjectView:
    """Filter/shape visible fields. Does not copy or fork canonical state."""

    modes = (mode,) if isinstance(mode, Mode) else tuple(mode)
    composed = compose_modes(modes)
    allowed = tuple(
        sorted(action.value for action in composed.allowed_actions if action in granted_actions)
    )
    return ProjectView(
        mode=modes,
        project_id=project_id,
        organization_id=organization_id,
        head_revision_id=live_head_revision_id(workspace, document_id),
        visible_fields=compose_visible_fields(modes),
        allowed_actions=allowed,
        principal_id=principal.actor_id,
    )
