"""Frozen OpenAPI v1 contract for the Integration Mesh."""

from __future__ import annotations

from typing import Any

from movie_muse.api.types import API_VERSION, OPENAPI_REQUIRED_PATHS


def openapi_v1() -> dict[str, Any]:
    paths: dict[str, Any] = {
        "/v1/projects/{project_id}": {
            "get": {"summary": "Read a project", "x-tool-side": "read"}
        },
        "/v1/projects/{project_id}/revisions": {
            "get": {"summary": "Read revision head", "x-tool-side": "read"}
        },
        "/v1/projects/{project_id}/proposals": {
            "get": {"summary": "List proposals", "x-tool-side": "read"},
            "post": {"summary": "Submit a proposal", "x-tool-side": "propose"},
        },
        "/v1/proposals/{proposal_id}/accept": {
            "post": {"summary": "Human commit of a proposal", "x-tool-side": "commit"}
        },
        "/v1/projects/{project_id}/artifacts": {
            "get": {"summary": "List approved artifacts", "x-tool-side": "read"}
        },
        "/v1/status": {"get": {"summary": "Project status", "x-tool-side": "read"}},
        "/v1/openapi.json": {"get": {"summary": "OpenAPI contract", "x-tool-side": "read"}},
        "/v1/capabilities": {
            "get": {"summary": "Capability registry", "x-tool-side": "read"}
        },
    }
    missing = [item for item in OPENAPI_REQUIRED_PATHS if item not in paths]
    if missing:
        raise RuntimeError(f"openapi contract missing paths: {missing}")
    return {
        "openapi": "3.0.3",
        "info": {"title": "Movie Muse Integration Mesh", "version": API_VERSION},
        "paths": paths,
        "x-compatibility": {
            "supported_versions": [API_VERSION],
            "unknown_fields": "ignore",
            "removed_fields": "breaking",
        },
    }
