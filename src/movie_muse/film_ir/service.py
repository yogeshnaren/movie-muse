"""Project deterministic FilmIR and route bounded extraction through ModelRouter."""

from __future__ import annotations

from typing import Any

from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.compiler.api import CompiledScreenplay, CompilerService
from movie_muse.film_ir.errors import AuthoredPromotionError, FilmIrNotFoundError
from movie_muse.film_ir.ids import (
    EXTRACTOR_VERSION,
    claim_id,
    entity_id,
    evidence_id,
    film_ir_id,
)
from movie_muse.film_ir.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.film_ir.metrics import ExtractionScores, score_against_compiler
from movie_muse.film_ir.repair import repair_extraction_output
from movie_muse.film_ir.types import CandidateSet, FilmIrProjection
from movie_muse.identity.api import Principal
from movie_muse.model_router.api import ModelRequest, ModelRouter
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.schemas.api import (
    EpistemicLevel,
    FilmIR,
    FilmIrEntity,
    FilmIrEntityKind,
    InferredClaim,
    ScreenplayDocument,
)

_KIND = {
    "character": FilmIrEntityKind.CHARACTER,
    "location": FilmIrEntityKind.LOCATION,
    "prop": FilmIrEntityKind.PROP,
    "scene": FilmIrEntityKind.SCENE,
    "event": FilmIrEntityKind.EVENT,
}


class FilmIrService:
    """Structural FilmIR from the compiler; inferred claims stay candidates."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        compiler: CompilerService,
        authorization: AuthorizationService,
        router: ModelRouter | None = None,
    ) -> None:
        self.workspace = workspace
        self.compiler = compiler
        self.authorization = authorization
        self.router = router

    def project(
        self,
        document: ScreenplayDocument,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> FilmIR:
        self._require_read(principal, document.project_id, acl_epoch)
        compiled = self.compiler.compile(document)
        film_ir = self._from_compiled(compiled)
        stored = self._persist(film_ir)
        return stored

    def get(self, film_ir_id_value: str) -> FilmIR:
        index = load_index(self.workspace)
        digest = index["digests"].get(film_ir_id_value)
        if digest is None:
            raise FilmIrNotFoundError(f"unknown film_ir: {film_ir_id_value}")
        return FilmIR.from_dict(load_payload(self.workspace, str(digest)))

    def get_for_revision(self, revision_id: str) -> FilmIR:
        index = load_index(self.workspace)
        stored_id = index["by_revision"].get(revision_id)
        if stored_id is None:
            raise FilmIrNotFoundError(f"no film_ir for revision {revision_id}")
        return self.get(str(stored_id))

    def extract_candidates(
        self,
        document: ScreenplayDocument,
        *,
        principal: Principal,
        acl_epoch: int,
        permission_snapshot_id: str,
        consent_granted: bool = True,
    ) -> FilmIrProjection:
        if self.router is None:
            raise AuthoredPromotionError("candidate extraction requires ModelRouter")
        film_ir = self.project(
            document, principal=principal, acl_epoch=acl_epoch
        )
        request = ModelRequest(
            capability="extract_structure",
            data_classification="internal",
            latency_budget_ms=5000,
            cost_budget=5.0,
            offline_required=True,
            context_tokens=256,
            structured_output=True,
            quality_tier="fast",
            role_contract="researcher",
            project_id=document.project_id,
            actor_id=principal.actor_id,
            acl_epoch=acl_epoch,
            permission_snapshot_id=permission_snapshot_id,
            input={"text": self._extraction_input(document)},
            consent_granted=consent_granted,
        )
        quote = self.router.quote(request)
        result = self.router.execute(request, quote_id=quote.id)
        repaired = repair_extraction_output(result.output)
        claims: list[InferredClaim] = []
        raw_entities: list[dict[str, str]] = []
        structural_names = {
            (entity.kind.value, entity.canonical_name.casefold())
            for entity in film_ir.entities
        }
        for row in repaired["entities"]:
            raw_entities.append(dict(row))
            kind = row["kind"]
            name = row["name"]
            if (kind, name.casefold()) in structural_names:
                continue
            claims.append(
                InferredClaim(
                    id=claim_id(kind, name, film_ir.source_revision_id),
                    subject_id=film_ir.id,
                    attribute=kind,
                    value=name,
                    confidence=0.5,
                    evidence_bundle_id=evidence_id(film_ir.id, kind, name),
                    model_id=result.provenance.model_version,
                )
            )
        candidates = CandidateSet(
            film_ir_id=film_ir.id,
            source_revision_id=film_ir.source_revision_id,
            model_id=result.provenance.model_version,
            claims=tuple(claims),
            raw_entities=tuple(raw_entities),
        )
        self._assert_no_authored_promotion(film_ir, candidates)
        return FilmIrProjection(film_ir=film_ir, candidates=candidates)

    def score(self, film_ir: FilmIR, compiled: CompiledScreenplay) -> ExtractionScores:
        return score_against_compiler(film_ir, compiled)

    def _from_compiled(self, compiled: CompiledScreenplay) -> FilmIR:
        entities = tuple(
            FilmIrEntity(
                id=entity_id(
                    entity.kind, entity.canonical_name, compiled.source_revision_id
                ),
                kind=_KIND[entity.kind],
                canonical_name=entity.canonical_name,
                scene_ids=entity.scene_ids,
                mention_block_ids=entity.mention_block_ids,
            )
            for entity in compiled.entities
            if entity.kind in _KIND
        )
        return FilmIR(
            id=film_ir_id(
                compiled.project_id, compiled.source_revision_id, EXTRACTOR_VERSION
            ),
            project_id=compiled.project_id,
            source_revision_id=compiled.source_revision_id,
            extractor_version=EXTRACTOR_VERSION,
            computed_at=utc_now(),
            entities=entities,
            scene_order=compiled.scene_order,
        )

    def _persist(self, film_ir: FilmIR) -> FilmIR:
        def write(index: dict[str, Any]) -> FilmIR:
            existing = index["by_revision"].get(film_ir.source_revision_id)
            if existing == film_ir.id and film_ir.id in index["digests"]:
                stored = FilmIR.from_dict(
                    load_payload(self.workspace, str(index["digests"][film_ir.id]))
                )
                return stored
            digest = put_payload(self.workspace, film_ir.to_dict())
            digests = dict(index["digests"])
            digests[film_ir.id] = digest
            index["digests"] = digests
            if film_ir.id not in list(index["ids"]):
                index["ids"] = [*list(index["ids"]), film_ir.id]
            by_revision = dict(index["by_revision"])
            by_revision[film_ir.source_revision_id] = film_ir.id
            index["by_revision"] = by_revision
            return film_ir

        return mutate_index(self.workspace, write)

    def _extraction_input(self, document: ScreenplayDocument) -> str:
        return "\n".join(block.text for block in document.blocks if block.text)

    def _assert_no_authored_promotion(
        self, film_ir: FilmIR, candidates: CandidateSet
    ) -> None:
        structural = {entity.canonical_name.casefold() for entity in film_ir.entities}
        for claim in candidates.claims:
            if claim.kind is not EpistemicLevel.INFERRED:
                raise AuthoredPromotionError("candidate claim is not inferred")
            # New names must not have been written onto FilmIR.
            if str(claim.value).casefold() not in structural:
                continue

    def _require_read(self, principal: Principal, project_id: str, acl_epoch: int) -> None:
        self.authorization.require(
            principal,
            Action.READ,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )
