"""Public surface of ``movie_muse.api``.

Hosts and other modules must import this module, never sibling internals.
The Integration Mesh is least-privilege: integrations may propose, not commit.
"""

from __future__ import annotations

from movie_muse.api.errors import (
    CommitDeniedError,
    CompatibilityError,
    CredentialError,
    IdempotencyConflictError,
    InjectionRejectedError,
    MeshError,
    MeshNotFoundError,
    RateLimitError,
    ReviewConnectorUnavailableError,
    SourceOfTruthError,
)
from movie_muse.api.injection import assert_no_injection
from movie_muse.api.openapi import openapi_v1
from movie_muse.api.sdk import (
    OpenFileFallback,
    ProductionReviewAdapter,
    example_client_flow,
    require_review_connector,
    review_connector_base_url,
)
from movie_muse.api.service import IntegrationMeshService
from movie_muse.api.types import (
    API_VERSION,
    CANON_FIELDS,
    EXTERNAL_FIELDS,
    FIELD_SOURCE_OF_TRUTH,
    OPENAPI_REQUIRED_PATHS,
    REVIEW_CONNECTOR_ENV,
    SUPPORTED_VERSIONS,
    CredentialStatus,
    IssuedToken,
    MeshCapability,
    ProjectStatus,
    SourceOfTruth,
    SyncRecord,
    ToolSide,
    VaultCredential,
)

__all__ = [
    "API_VERSION",
    "CANON_FIELDS",
    "EXTERNAL_FIELDS",
    "FIELD_SOURCE_OF_TRUTH",
    "OPENAPI_REQUIRED_PATHS",
    "REVIEW_CONNECTOR_ENV",
    "SUPPORTED_VERSIONS",
    "CommitDeniedError",
    "CompatibilityError",
    "CredentialError",
    "CredentialStatus",
    "IdempotencyConflictError",
    "InjectionRejectedError",
    "IssuedToken",
    "IntegrationMeshService",
    "MeshCapability",
    "MeshError",
    "MeshNotFoundError",
    "OpenFileFallback",
    "ProductionReviewAdapter",
    "ProjectStatus",
    "RateLimitError",
    "ReviewConnectorUnavailableError",
    "SourceOfTruth",
    "SourceOfTruthError",
    "SyncRecord",
    "ToolSide",
    "VaultCredential",
    "assert_no_injection",
    "example_client_flow",
    "openapi_v1",
    "require_review_connector",
    "review_connector_base_url",
]
