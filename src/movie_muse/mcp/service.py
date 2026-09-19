"""MCP tools over the Integration Mesh. Commit stays human-only."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from movie_muse.api.api import IntegrationMeshService, ToolSide, assert_no_injection
from movie_muse.identity.api import Principal
from movie_muse.mcp.errors import ToolSideError, UnknownToolError
from movie_muse.mcp.types import (
    MCP_TOOLS,
    TOOL_ARTIFACTS_READ,
    TOOL_PROJECTS_READ,
    TOOL_PROPOSALS_READ,
    TOOL_REVISIONS_READ,
    TOOL_STATUS_READ,
    McpTool,
)
from movie_muse.schemas.api import ChangeSet


class MeshMcpService:
    """Permissioned MCP catalog. Tools declare read, propose, or commit."""

    def __init__(self, mesh: IntegrationMeshService) -> None:
        self.mesh = mesh
        self._by_name = {item.name: item for item in MCP_TOOLS}

    def tools(self) -> tuple[McpTool, ...]:
        return MCP_TOOLS

    def tool(self, name: str) -> McpTool:
        found = self._by_name.get(name)
        if found is None:
            raise UnknownToolError(f"unknown MCP tool {name}")
        return found

    def invoke(
        self,
        name: str,
        arguments: Mapping[str, Any],
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> dict[str, Any]:
        spec = self.tool(name)
        self._scan_arguments(arguments)
        project_id = str(arguments.get("project_id") or "")
        if spec.side is ToolSide.READ:
            return self._invoke_read(spec.name, project_id, principal, acl_epoch)
        if spec.side is ToolSide.PROPOSE:
            return self._invoke_propose(arguments, principal, acl_epoch)
        if spec.side is ToolSide.COMMIT:
            return self._invoke_commit(arguments, principal, acl_epoch)
        raise ToolSideError(f"unsupported tool side {spec.side.value}")

    def _invoke_read(
        self, name: str, project_id: str, principal: Principal, acl_epoch: int
    ) -> dict[str, Any]:
        if name == TOOL_PROJECTS_READ:
            return self.mesh.get_project(project_id, principal=principal, acl_epoch=acl_epoch)
        if name == TOOL_REVISIONS_READ:
            return self.mesh.get_revision_head(project_id, principal=principal, acl_epoch=acl_epoch)
        if name == TOOL_PROPOSALS_READ:
            ids = self.mesh.list_proposals(project_id, principal=principal, acl_epoch=acl_epoch)
            return {"proposal_ids": list(ids)}
        if name == TOOL_ARTIFACTS_READ:
            ids = self.mesh.list_approved_artifacts(
                project_id, principal=principal, acl_epoch=acl_epoch
            )
            return {"artifact_version_ids": list(ids)}
        if name == TOOL_STATUS_READ:
            return self.mesh.status(project_id, principal=principal, acl_epoch=acl_epoch).to_dict()
        raise UnknownToolError(name)

    def _invoke_propose(
        self, arguments: Mapping[str, Any], principal: Principal, acl_epoch: int
    ) -> dict[str, Any]:
        change_set = arguments.get("change_set")
        if not isinstance(change_set, ChangeSet):
            raise ToolSideError("proposals.propose requires a ChangeSet")
        envelope = self.mesh.propose(
            str(arguments["project_id"]),
            change_set,
            principal=principal,
            acl_epoch=acl_epoch,
            intent=str(arguments.get("intent") or "mesh.mcp.propose"),
            rationale_summary=str(arguments.get("rationale_summary") or "mcp propose"),
            provenance=str(arguments.get("provenance") or "mcp"),
            extra_payload=arguments,
        )
        return {"proposal_id": envelope.proposal.id, "status": envelope.proposal.status.value}

    def _invoke_commit(
        self, arguments: Mapping[str, Any], principal: Principal, acl_epoch: int
    ) -> dict[str, Any]:
        return self.mesh.commit(
            str(arguments["proposal_id"]),
            principal=principal,
            acl_epoch=acl_epoch,
        )

    def _scan_arguments(self, arguments: Mapping[str, Any]) -> None:
        parts: list[str] = []
        for value in arguments.values():
            if isinstance(value, str):
                parts.append(value)
        if parts:
            assert_no_injection(*parts)
