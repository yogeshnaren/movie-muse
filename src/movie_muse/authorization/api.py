"""Public surface of ``movie_muse.authorization``.

Hosts and other modules must import this module, never sibling internals.
"""

from __future__ import annotations

from movie_muse.authorization.errors import AuthorizationError
from movie_muse.authorization.policy import (
    MODE_ACTIONS,
    MODE_VISIBLE_FIELDS,
    ROLE_ACTIONS,
    compose_mode_actions,
    craft_decision_allowed,
    role_allows,
)
from movie_muse.authorization.projections import compose_modes, live_head_revision_id, project_view
from movie_muse.authorization.service import AuthorizationService, authorize
from movie_muse.authorization.types import (
    Action,
    AuthContext,
    ComposedMode,
    Decision,
    DecisionEffect,
    Mode,
    ProjectView,
    Resource,
    ResourceKind,
    parse_action,
    parse_resource_kind,
)
from movie_muse.authorization.wrapper import AuthorizedRevisionService

__all__ = [
    "Action",
    "AuthContext",
    "AuthorizationError",
    "AuthorizationService",
    "AuthorizedRevisionService",
    "ComposedMode",
    "Decision",
    "DecisionEffect",
    "MODE_ACTIONS",
    "MODE_VISIBLE_FIELDS",
    "Mode",
    "ProjectView",
    "ROLE_ACTIONS",
    "Resource",
    "ResourceKind",
    "authorize",
    "compose_mode_actions",
    "compose_modes",
    "craft_decision_allowed",
    "live_head_revision_id",
    "parse_action",
    "parse_resource_kind",
    "project_view",
    "role_allows",
]
