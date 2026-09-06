"""Offline golden-path project seed: document, revision head, rights, tiny DAG."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from movie_muse.audit.api import AuditLog
from movie_muse.authorization.api import AuthorizationService
from movie_muse.dependencies.api import DependencyEngine, NodeKind, StoredNode
from movie_muse.identity.api import Actor, IdentityService, Organization, Principal, PrincipalKind
from movie_muse.jobs.api import JobService
from movie_muse.persistence.api import LocalWorkspace
from movie_muse.revisions.api import RevisionService
from movie_muse.rights.api import PermittedUse, RightsService, SourceClassification, SourceVersion
from movie_muse.schemas.api import Project, ScreenplayDocument
from movie_muse.testkit.catalog import FixtureCatalog, load_rights_fixture
from movie_muse.testkit.paths import golden_path_root


@dataclass
class GoldenPathProject:
    workspace: LocalWorkspace
    identity: IdentityService
    authorization: AuthorizationService
    audit: AuditLog
    revisions: RevisionService
    rights: RightsService
    jobs: JobService
    dependencies: DependencyEngine
    project: Project
    document: ScreenplayDocument
    owner: Actor
    licensed_source: SourceVersion
    unlicensed_source: SourceVersion
    revision_head_id: str
    source_node: StoredNode
    rights_node: StoredNode
    derived_node: StoredNode

    @property
    def principal(self) -> Principal:
        return self.identity.principal(self.owner.id)

    @property
    def epoch(self) -> int:
        return self.identity.acl_epoch()


def _seed_meta(root: Path | None) -> dict[str, Any]:
    path = golden_path_root(root) / "MANIFEST.yaml"
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("golden_path/MANIFEST.yaml must contain a mapping")
    return loaded


def load_golden_path_project(
    workspace: LocalWorkspace, *, repo_root: Path | None = None
) -> GoldenPathProject:
    """Open a feature-complete document with revision, rights, and a tiny graph.

    Airplane/offline safe: sets connectivity_offline before any local writes.
    Does not call network providers.
    """

    workspace.set_airplane_mode(True)
    meta = _seed_meta(repo_root)
    catalog = FixtureCatalog(repo_root)
    fixture = catalog.get(str(meta["fixture_id"]))
    document = fixture.document
    project = Project.from_dict(
        {
            "id": document.project_id,
            "organization_id": str(meta["organization_id"]),
            "title": str(meta.get("project_title") or document.title),
            "owner_actor_id": str(meta["owner_actor_id"]),
            "created_at": str(meta["created_at"]),
        }
    )
    branch_id = str(meta["branch_id"])
    workspace.open_project(project, document, branch_id=branch_id)
    identity = IdentityService(workspace)
    owner = Actor(
        id=project.owner_actor_id,
        display_name=str(meta.get("owner_display_name") or "Golden Path Owner"),
        principal_kind=PrincipalKind.HUMAN,
        organization_id=project.organization_id,
        created_at=project.created_at,
    )
    identity.bootstrap(
        organization=Organization(
            id=project.organization_id,
            name=str(meta.get("organization_name") or "Golden Path Studio"),
            created_at=project.created_at,
        ),
        project=project,
        owner=owner,
    )
    audit = AuditLog(workspace)
    authorization = AuthorizationService(workspace, identity, audit=audit)
    revisions = RevisionService(workspace)
    revisions.bind(actor_id=owner.id)
    jobs = JobService(
        workspace,
        identity,
        authorization,
        audit,
        lambda job: job.input_fingerprint,
    )
    rights = RightsService(workspace, authorization, audit)
    dependencies = DependencyEngine(workspace, authorization, jobs, audit)
    principal = identity.principal(owner.id)
    epoch = identity.acl_epoch()
    licensed_def = load_rights_fixture("licensed", root=repo_root)
    unlicensed_def = load_rights_fixture("unlicensed", root=repo_root)
    licensed = rights.register_source(
        project_id=project.id,
        title=str(licensed_def["title"]),
        classification=SourceClassification(str(licensed_def["classification"])),
        principal=principal,
        acl_epoch=epoch,
        permitted_uses=tuple(PermittedUse(str(item)) for item in licensed_def["permitted_uses"]),
        license_summary=str(licensed_def.get("license_summary") or licensed_def.get("license")),
        license_expiry=str(licensed_def["license_expiry"]) if licensed_def.get("license_expiry") else None,
        allow_training=False,
        source_id=str(licensed_def["source_id"]) if licensed_def.get("source_id") else None,
    )
    unlicensed = rights.register_source(
        project_id=project.id,
        title=str(unlicensed_def["title"]),
        classification=SourceClassification(str(unlicensed_def["classification"])),
        principal=principal,
        acl_epoch=epoch,
        permitted_uses=(),
        source_id=str(unlicensed_def["source_id"]) if unlicensed_def.get("source_id") else None,
    )
    head = revisions.canon_head_id()
    source_node = dependencies.add_node(
        project_id=project.id,
        kind=NodeKind.SOURCE_REVISION,
        principal=principal,
        acl_epoch=epoch,
        subject_id=head,
        content_hash=head,
    )
    rights_node = dependencies.add_node(
        project_id=project.id,
        kind=NodeKind.RIGHTS_RECORD,
        principal=principal,
        acl_epoch=epoch,
        subject_id=licensed.source_id,
        content_hash=licensed.id,
    )
    derived = dependencies.add_node(
        project_id=project.id,
        kind=NodeKind.DERIVED_PROJECTION,
        principal=principal,
        acl_epoch=epoch,
        input_ids=(source_node.id, rights_node.id),
        subject_id=document.id,
    )
    return GoldenPathProject(
        workspace=workspace,
        identity=identity,
        authorization=authorization,
        audit=audit,
        revisions=revisions,
        rights=rights,
        jobs=jobs,
        dependencies=dependencies,
        project=project,
        document=document,
        owner=owner,
        licensed_source=licensed,
        unlicensed_source=unlicensed,
        revision_head_id=head,
        source_node=source_node,
        rights_node=rights_node,
        derived_node=derived,
    )
