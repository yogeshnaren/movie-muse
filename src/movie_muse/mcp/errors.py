"""Typed failures for MCP tools."""

from __future__ import annotations


class McpError(RuntimeError):
    """Base class for MCP mesh failures."""


class UnknownToolError(McpError):
    """The named MCP tool is not in the registry."""


class ToolSideError(McpError):
    """A commit tool was invoked as propose, or the reverse."""
