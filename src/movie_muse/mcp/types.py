"""MCP tool catalog. Each tool is read, propose, or commit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from movie_muse.api.api import ToolSide

TOOL_PROJECTS_READ = "projects.read"
TOOL_REVISIONS_READ = "revisions.read"
TOOL_PROPOSALS_READ = "proposals.read"
TOOL_PROPOSALS_PROPOSE = "proposals.propose"
TOOL_PROPOSALS_COMMIT = "proposals.commit"
TOOL_ARTIFACTS_READ = "artifacts.read_approved"
TOOL_STATUS_READ = "status.read"


@dataclass(frozen=True, slots=True)
class McpTool:
    name: str
    side: ToolSide
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "side": self.side.value,
            "description": self.description,
        }


MCP_TOOLS: tuple[McpTool, ...] = (
    McpTool(TOOL_PROJECTS_READ, ToolSide.READ, "Read project identity"),
    McpTool(TOOL_REVISIONS_READ, ToolSide.READ, "Read current revision head"),
    McpTool(TOOL_PROPOSALS_READ, ToolSide.READ, "List proposals"),
    McpTool(TOOL_PROPOSALS_PROPOSE, ToolSide.PROPOSE, "Submit a proposal; does not write canon"),
    McpTool(TOOL_PROPOSALS_COMMIT, ToolSide.COMMIT, "Human-only accept of a pending proposal"),
    McpTool(TOOL_ARTIFACTS_READ, ToolSide.READ, "List approved artifact versions"),
    McpTool(TOOL_STATUS_READ, ToolSide.READ, "Read project status"),
)
