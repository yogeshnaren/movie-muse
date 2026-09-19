"""Public surface of ``movie_muse.mcp``.

Hosts must import this module, never sibling internals.
MCP tools distinguish read, propose, and commit.
"""

from __future__ import annotations

from movie_muse.mcp.errors import McpError, ToolSideError, UnknownToolError
from movie_muse.mcp.service import MeshMcpService
from movie_muse.mcp.types import MCP_TOOLS, McpTool

__all__ = [
    "MCP_TOOLS",
    "McpError",
    "McpTool",
    "MeshMcpService",
    "ToolSideError",
    "UnknownToolError",
]
