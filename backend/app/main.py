from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from movie_muse.api.api import IntegrationMeshService
from movie_muse.api.errors import CommitDeniedError, CredentialError
from movie_muse.authorization.api import AuthorizationError
from movie_muse.identity.api import IdentityService
from movie_muse.webhooks.api import (
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    WebhookReplayError,
    WebhookService,
    WebhookSignatureError,
)

app = FastAPI(title="Movie Muse API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _mesh() -> IntegrationMeshService:
    mesh = getattr(app.state, "mesh", None)
    if mesh is None:
        raise HTTPException(status_code=503, detail="integration mesh is not bound")
    return mesh


def _webhooks() -> WebhookService:
    service = getattr(app.state, "webhooks", None)
    if service is None:
        raise HTTPException(status_code=503, detail="webhooks are not bound")
    return service


def _identity() -> IdentityService:
    identity = getattr(app.state, "identity", None)
    if identity is None:
        raise HTTPException(status_code=503, detail="identity is not bound")
    return identity


def _principal(token: str | None):
    if not token:
        raise HTTPException(status_code=401, detail="missing mesh token")
    try:
        credential = _mesh().authenticate_token(token)
    except CredentialError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return _identity().principal(credential.actor_id)


def bind_mesh(
    mesh: IntegrationMeshService,
    *,
    identity: IdentityService,
    webhooks: WebhookService | None = None,
) -> None:
    app.state.mesh = mesh
    app.state.identity = identity
    if webhooks is not None:
        app.state.webhooks = webhooks


@app.get("/health")
async def health():
    """Simple liveness probe."""
    return {"status": "ok"}


@app.get("/v1/openapi.json")
async def openapi_contract():
    return _mesh().openapi()


@app.get("/v1/status")
async def status(
    project_id: str,
    x_movie_muse_token: str | None = Header(default=None, alias="X-Movie-Muse-Token"),
):
    try:
        return _mesh().status(
            project_id,
            principal=_principal(x_movie_muse_token),
            acl_epoch=_identity().acl_epoch(),
        ).to_dict()
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/v1/projects/{project_id}")
async def get_project(
    project_id: str,
    x_movie_muse_token: str | None = Header(default=None, alias="X-Movie-Muse-Token"),
):
    try:
        return _mesh().get_project(
            project_id,
            principal=_principal(x_movie_muse_token),
            acl_epoch=_identity().acl_epoch(),
        )
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/v1/projects/{project_id}/revisions")
async def get_revisions(
    project_id: str,
    x_movie_muse_token: str | None = Header(default=None, alias="X-Movie-Muse-Token"),
):
    try:
        return _mesh().get_revision_head(
            project_id,
            principal=_principal(x_movie_muse_token),
            acl_epoch=_identity().acl_epoch(),
        )
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/v1/projects/{project_id}/proposals")
async def list_proposals(
    project_id: str,
    x_movie_muse_token: str | None = Header(default=None, alias="X-Movie-Muse-Token"),
):
    try:
        ids = _mesh().list_proposals(
            project_id,
            principal=_principal(x_movie_muse_token),
            acl_epoch=_identity().acl_epoch(),
        )
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"proposal_ids": list(ids)}


@app.get("/v1/projects/{project_id}/artifacts")
async def list_artifacts(
    project_id: str,
    x_movie_muse_token: str | None = Header(default=None, alias="X-Movie-Muse-Token"),
):
    try:
        ids = _mesh().list_approved_artifacts(
            project_id,
            principal=_principal(x_movie_muse_token),
            acl_epoch=_identity().acl_epoch(),
        )
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"artifact_version_ids": list(ids)}


@app.get("/v1/capabilities")
async def capabilities(
    x_movie_muse_token: str | None = Header(default=None, alias="X-Movie-Muse-Token"),
):
    _principal(x_movie_muse_token)
    return {"capabilities": [item.to_dict() for item in _mesh().list_capabilities()]}


@app.post("/v1/proposals/{proposal_id}/accept")
async def accept_proposal(
    proposal_id: str,
    x_movie_muse_token: str | None = Header(default=None, alias="X-Movie-Muse-Token"),
):
    try:
        return _mesh().commit(
            proposal_id,
            principal=_principal(x_movie_muse_token),
            acl_epoch=_identity().acl_epoch(),
        )
    except (AuthorizationError, CommitDeniedError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/v1/webhooks/inbound")
async def inbound_webhook(
    request: Request,
    project_id: str,
    x_movie_muse_token: str | None = Header(default=None, alias="X-Movie-Muse-Token"),
    x_movie_muse_signature: str | None = Header(default=None, alias=SIGNATURE_HEADER),
    x_movie_muse_timestamp: str | None = Header(default=None, alias=TIMESTAMP_HEADER),
):
    body = await request.body()
    headers = {
        SIGNATURE_HEADER: x_movie_muse_signature or "",
        TIMESTAMP_HEADER: x_movie_muse_timestamp or "",
    }
    try:
        delivery = _webhooks().ingest(
            project_id,
            headers=headers,
            body=body,
            principal=_principal(x_movie_muse_token),
            acl_epoch=_identity().acl_epoch(),
        )
    except (WebhookSignatureError, WebhookReplayError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return delivery.to_dict()
