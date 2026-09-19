"""Advisory visual language. Correlations are not causation. ShotIR stays proposed."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService
from movie_muse.identity.api import Principal, PrincipalKind
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.rights.api import PermittedUse, RightsService
from movie_muse.schemas.api import new_ulid
from movie_muse.shot_ir.api import ShotIRService, StoredShot
from movie_muse.visual_language.errors import (
    CausationClaimError,
    LanguageNotFoundError,
    SafetyReviewError,
    ShotProposalError,
    UncitedReferenceError,
)
from movie_muse.visual_language.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.visual_language.types import (
    DISCLAIMER,
    FORBIDDEN_CAUSATION_PHRASES,
    EvolutionStep,
    LanguageRule,
    PaletteSwatch,
    SafetyReview,
    ShotColorProposal,
    VisualLanguage,
)


class VisualLanguageService:
    """Palettes and rules. References must be cited. ShotIR updates are proposals."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        rights: RightsService,
        shots: ShotIRService,
        *,
        clock: Callable[[], str] = utc_now,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.rights = rights
        self.shots = shots
        self.clock = clock

    def record_language(
        self,
        *,
        project_id: str,
        palette: Sequence[PaletteSwatch],
        contrast: str,
        saturation: str,
        temperature: str,
        source_motivation: str,
        lighting_ratio: str,
        production_design: str,
        wardrobe: str,
        skin_tone_rendering: str,
        lens_render_interaction: str,
        composition: str,
        temporal_progression: str,
        safety: SafetyReview,
        principal: Principal,
        acl_epoch: int,
        rules: Sequence[LanguageRule] = (),
        evolution: Sequence[EvolutionStep] = (),
        reference_source_ids: Sequence[str] = (),
    ) -> VisualLanguage:
        self._require(principal, Action.PROPOSE, project_id, acl_epoch)
        self._assert_safety(safety)
        self._cite_references(reference_source_ids, principal, acl_epoch)
        language = VisualLanguage(
            id=f"vln_{new_ulid()}",
            project_id=project_id,
            contrast=contrast,
            saturation=saturation,
            temperature=temperature,
            source_motivation=source_motivation,
            lighting_ratio=lighting_ratio,
            production_design=production_design,
            wardrobe=wardrobe,
            skin_tone_rendering=skin_tone_rendering,
            lens_render_interaction=lens_render_interaction,
            composition=composition,
            temporal_progression=temporal_progression,
            palette=tuple(palette),
            rules=tuple(rules),
            evolution=tuple(evolution),
            reference_source_ids=tuple(reference_source_ids),
            safety=safety,
        )
        self._assert_not_causation(self._export_text(language))
        written = self._put_language(language)
        self._audit(principal, acl_epoch, "visual_language.record", written.id, "advisory")
        return written

    def get_language(
        self, language_id: str, *, principal: Principal, acl_epoch: int
    ) -> VisualLanguage:
        stored = self._load_language(language_id)
        self._require(principal, Action.READ, stored.project_id, acl_epoch)
        return stored

    def export_language(
        self, language_id: str, *, principal: Principal, acl_epoch: int
    ) -> str:
        stored = self.get_language(language_id, principal=principal, acl_epoch=acl_epoch)
        text = self._export_text(stored)
        self._assert_not_causation(text)
        self._audit(principal, acl_epoch, "visual_language.export", stored.id, "advisory")
        return text

    def propose_shot_color(
        self,
        language_id: str,
        shot_id: str,
        *,
        principal: Principal,
        acl_epoch: int,
    ) -> ShotColorProposal:
        stored = self.get_language(language_id, principal=principal, acl_epoch=acl_epoch)
        self._require(principal, Action.PROPOSE, stored.project_id, acl_epoch)
        self._assert_safety(stored.safety)
        shot = self.shots.get_shot(shot_id, principal=principal, acl_epoch=acl_epoch)
        if shot.project_id != stored.project_id:
            raise ShotProposalError("shot and visual language must share a project")
        key = next((item.name for item in stored.palette if item.role == "key"), "unspecified")
        color_intent = (
            f"{stored.temperature} {key} key; contrast {stored.contrast}; "
            f"skin-tone {stored.skin_tone_rendering}"
        )
        proposal = ShotColorProposal(
            id=f"vpr_{new_ulid()}",
            language_id=stored.id,
            shot_id=shot.record.id,
            color_intent=color_intent,
            accepted=False,
        )
        written = self._put_proposal(proposal)
        self._audit(principal, acl_epoch, "visual_language.propose_shot", written.id, shot_id)
        return written

    def accept_shot_proposal(
        self, proposal_id: str, *, principal: Principal, acl_epoch: int
    ) -> StoredShot:
        if principal.kind is not PrincipalKind.HUMAN:
            raise ShotProposalError("only a human principal may accept a ShotIR color proposal")
        proposal = self._load_proposal(proposal_id)
        language = self.get_language(
            proposal.language_id, principal=principal, acl_epoch=acl_epoch
        )
        self._require(principal, Action.ACCEPT, language.project_id, acl_epoch)
        if proposal.accepted:
            raise ShotProposalError("shot color proposal is already accepted")
        updated = self.shots.update_camera(
            proposal.shot_id,
            principal=principal,
            acl_epoch=acl_epoch,
            color_intent=proposal.color_intent,
        )
        self._put_proposal(
            ShotColorProposal(
                id=proposal.id,
                language_id=proposal.language_id,
                shot_id=proposal.shot_id,
                color_intent=proposal.color_intent,
                accepted=True,
            )
        )
        self._audit(principal, acl_epoch, "visual_language.accept_shot", proposal.id, updated.record.id)
        return updated

    def _cite_references(
        self, source_ids: Sequence[str], principal: Principal, acl_epoch: int
    ) -> None:
        del principal, acl_epoch
        if not source_ids:
            raise UncitedReferenceError("visual language requires at least one cited reference")
        for source_id in source_ids:
            try:
                self.rights.require_permitted_use(source_id, PermittedUse.CITATION)
            except Exception as exc:
                raise UncitedReferenceError(
                    f"reference {source_id} is not permitted for citation"
                ) from exc

    @staticmethod
    def _assert_safety(safety: SafetyReview) -> None:
        if not safety.skin_tone_safe or not safety.accessibility_ok:
            raise SafetyReviewError(
                "skin-tone and accessibility review must pass before visual-language use"
            )

    @staticmethod
    def _assert_not_causation(text: str) -> None:
        lowered = text.casefold()
        if "not claimed as causation" not in lowered:
            raise CausationClaimError("export must state that correlation is not causation")
        for phrase in FORBIDDEN_CAUSATION_PHRASES:
            if phrase in lowered:
                raise CausationClaimError(
                    "visual language must not claim palette correlation as causation"
                )

    @staticmethod
    def _export_text(stored: VisualLanguage) -> str:
        rule_lines = []
        for item in stored.rules:
            rule_lines.append(f"{item.kind.value.upper()}\t{item.dimension}\t{item.text}")
        palette = ", ".join(f"{item.role}:{item.name}" for item in stored.palette) or "none"
        return "\n".join(
            [
                DISCLAIMER,
                f"LANGUAGE {stored.id}",
                f"PALETTE {palette}",
                f"CONTRAST {stored.contrast}",
                f"SATURATION {stored.saturation}",
                f"TEMPERATURE {stored.temperature}",
                f"SOURCE_MOTIVATION {stored.source_motivation}",
                f"LIGHTING_RATIO {stored.lighting_ratio}",
                f"PRODUCTION_DESIGN {stored.production_design}",
                f"WARDROBE {stored.wardrobe}",
                f"SKIN_TONE {stored.skin_tone_rendering}",
                f"LENS_RENDER {stored.lens_render_interaction}",
                f"COMPOSITION {stored.composition}",
                f"TEMPORAL {stored.temporal_progression}",
                f"REFERENCES {','.join(stored.reference_source_ids)}",
                *rule_lines,
            ]
        )

    def _load_language(self, language_id: str) -> VisualLanguage:
        index = load_index(self.workspace)
        digest = dict(index.get("language_digests", {})).get(language_id)
        if digest is None:
            raise LanguageNotFoundError(f"visual language {language_id} is not in the index")
        return VisualLanguage.from_dict(load_payload(self.workspace, str(digest)))

    def _load_proposal(self, proposal_id: str) -> ShotColorProposal:
        index = load_index(self.workspace)
        digest = dict(index.get("proposal_digests", {})).get(proposal_id)
        if digest is None:
            raise ShotProposalError(f"shot color proposal {proposal_id} is not in the index")
        return ShotColorProposal.from_dict(load_payload(self.workspace, str(digest)))

    def _put_language(self, stored: VisualLanguage) -> VisualLanguage:
        def persist(index: dict[str, Any]) -> VisualLanguage:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("language_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["language_ids"] = ids
            digests = dict(index.get("language_digests", {}))
            digests[stored.id] = digest
            index["language_digests"] = digests
            by_project = dict(index.get("by_project", {}))
            project_ids = list(by_project.get(stored.project_id, []))
            if stored.id not in project_ids:
                project_ids.append(stored.id)
            by_project[stored.project_id] = project_ids
            index["by_project"] = by_project
            return stored

        return mutate_index(self.workspace, persist)

    def _put_proposal(self, stored: ShotColorProposal) -> ShotColorProposal:
        def persist(index: dict[str, Any]) -> ShotColorProposal:
            digest = put_payload(self.workspace, stored.to_dict())
            ids = list(index.get("proposal_ids", []))
            if stored.id not in ids:
                ids.append(stored.id)
            index["proposal_ids"] = ids
            digests = dict(index.get("proposal_digests", {}))
            digests[stored.id] = digest
            index["proposal_digests"] = digests
            by_shot = dict(index.get("by_shot", {}))
            shot_ids = list(by_shot.get(stored.shot_id, []))
            if stored.id not in shot_ids:
                shot_ids.append(stored.id)
            by_shot[stored.shot_id] = shot_ids
            index["by_shot"] = by_shot
            return stored

        return mutate_index(self.workspace, persist)

    def _require(
        self, principal: Principal, action: Action, project_id: str, acl_epoch: int
    ) -> None:
        self.authorization.require(
            principal,
            action,
            self.authorization.resource_for_project(project_id),
            acl_epoch=acl_epoch,
        )

    def _audit(
        self,
        principal: Principal,
        acl_epoch: int,
        operation: str,
        object_id: str,
        reason: str,
    ) -> None:
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation=operation,
            object_kind="visual_language",
            object_id=object_id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=reason,
        )
