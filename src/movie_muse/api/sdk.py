"""Adapter SDK: specialist production/review connector plus open-file fallback."""

from __future__ import annotations

import os
from pathlib import Path

from movie_muse.api.errors import ReviewConnectorUnavailableError
from movie_muse.api.types import REVIEW_CONNECTOR_ENV
from movie_muse.artifacts.api import ArtifactService
from movie_muse.identity.api import Principal


def review_connector_base_url() -> str | None:
    value = os.environ.get(REVIEW_CONNECTOR_ENV, "").strip()
    return value or None


def require_review_connector() -> str:
    base = review_connector_base_url()
    if not base:
        raise ReviewConnectorUnavailableError(
            f"{REVIEW_CONNECTOR_ENV} is unset; live specialist connector stays "
            "NOT_RUN (fail-closed, not skipped; mocks do not satisfy the live gate)"
        )
    return base


class ProductionReviewAdapter:
    """Replaceable production/review connector. Live URL is never mocked."""

    def push_approved(
        self,
        artifact_version_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> str:
        del artifact_version_id, principal, acl_epoch
        require_review_connector()
        raise ReviewConnectorUnavailableError(
            "specialist review push is not completed without a live connector"
        )


class OpenFileFallback:
    """Export an approved artifact version when APIs are unavailable."""

    def __init__(self, artifacts: ArtifactService) -> None:
        self.artifacts = artifacts

    def export_approved(
        self,
        artifact_version_id: str,
        destination: Path,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> Path:
        return self.artifacts.export_version(
            artifact_version_id,
            destination,
            principal=principal,
            acl_epoch=acl_epoch,
        )


def example_client_flow() -> dict[str, str]:
    """Documented SDK example: read, propose, human commit, open-file fallback."""

    return {
        "read": "GET /v1/projects/{project_id}",
        "propose": "POST /v1/projects/{project_id}/proposals",
        "commit": "POST /v1/proposals/{proposal_id}/accept",
        "fallback": "OpenFileFallback.export_approved",
        "live_connector": REVIEW_CONNECTOR_ENV,
    }
