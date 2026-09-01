"""RevisionService: immutable history, branches, checkpoints, merges, proposals."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from movie_muse.document.api import InvalidOperationError, apply_change_set, structural_diff
from movie_muse.persistence.api import LocalWorkspace, SaveAck, utc_now
from movie_muse.revisions.errors import (
    ArchivedBranchError,
    CheckpointExistsError,
    MergeConflictError,
    ProtectedBranchError,
    RebaseError,
    ReplayError,
    RevisionError,
    RevisionNotFoundError,
    StaleBaseError,
    StaleProposalError,
)
from movie_muse.revisions.events import make_project_event
from movie_muse.revisions.index import (
    clone_index,
    commit_index,
    empty_index,
    load_index,
    load_json_blob,
    put_json_blob,
)
from movie_muse.revisions.merge import (
    compose_operations,
    content_equal,
    copy_operation,
    diff_against_base,
    effective_operations,
    operation_target_keys,
    overlapping_targets,
    snapshot_for_diff,
    try_apply,
)
from movie_muse.revisions.projection import (
    render_diff_text,
    render_history_html,
    render_history_text,
    stabilize_diff_change_set,
)
from movie_muse.revisions.types import (
    Branch,
    Checkpoint,
    DiffProjection,
    HistoryProjection,
    HistoryRecord,
    Merge,
    MergeConflict,
    MergeResolution,
    RevisionRecord,
)
from movie_muse.schemas.api import (
    ChangeSet,
    ProjectEvent,
    Proposal,
    ProposalStatus,
    RevalidationRecord,
    ScreenplayDocument,
    compute_integrity_hash,
    new_id,
    new_ulid,
    to_json_dict,
)

MUTATING_KINDS = frozenset(
    {
        "patch_accepted",
        "merge_completed",
        "proposal_accepted",
        "restore_completed",
    }
)
DEFAULT_DEVICE_ID = "dev_local"
DEFAULT_BRANCH_NAME = "main"


class RevisionService:
    """Public command surface wrapping a ``LocalWorkspace``.

    Document revisions are the immutable rows/blobs created by ``workspace.save``.
    Branches, checkpoints, merges, proposals, and ProjectEvents are stored as
    content-addressed blobs addressed from a revisions-owned ``workspace_meta``
    index. History objects are never updated in place.
    """

    def __init__(self, workspace: LocalWorkspace) -> None:
        self.workspace = workspace

    def bind(self, *, actor_id: str | None = None) -> Branch:
        """Persist the canonical branch from the already-open workspace if needed."""

        index = self._ensure_index(actor_id=actor_id, persist=True)
        return self._branch_from_index(index, str(index["canonical_branch_id"]))

    def canon_branch(self) -> Branch:
        index = self._ensure_index()
        return self._branch_from_index(index, str(index["canonical_branch_id"]))

    def canon_head_id(self) -> str:
        return self.canon_branch().head_revision_id

    def get_branch(self, branch_ref: str) -> Branch:
        index = self._ensure_index()
        return self._resolve_branch(index, branch_ref)

    def list_branches(self) -> tuple[Branch, ...]:
        index = self._ensure_index()
        branches = [Branch.from_dict(raw) for raw in index["branches"].values()]
        return tuple(sorted(branches, key=lambda branch: branch.name))

    def create_branch(
        self,
        name: str,
        *,
        actor_id: str,
        from_branch: str | None = None,
        from_revision_id: str | None = None,
        protected: bool = False,
    ) -> Branch:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        if name in index["branch_names"]:
            raise RevisionError(f"branch name already exists: {name}")
        if from_revision_id is not None:
            head = from_revision_id
            self._revision_record(head)
        else:
            source = self._resolve_branch(index, from_branch or str(index["canonical_branch_id"]))
            head = source.head_revision_id
        now = utc_now()
        branch = Branch(
            id=self._new_branch_id(),
            name=name,
            head_revision_id=head,
            project_id=str(index["project_id"]),
            created_at=now,
            protected=protected,
            archived=False,
        )
        index = clone_index(index)
        index["branches"][branch.id] = branch.to_dict()
        index["branch_names"][name] = branch.id
        event = self._event(
            index,
            branch_id=branch.id,
            result_revision_id=head,
            actor_id=actor_id,
            base_revision_id=head,
            payload={"kind": "branch_created", "name": name, "protected": protected},
        )
        self._commit_with_event(index, event)
        return branch

    def retarget_branch(
        self,
        branch_ref: str,
        revision_id: str,
        *,
        actor_id: str,
        allow_protected: bool = False,
    ) -> Branch:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        branch = self._resolve_branch(index, branch_ref)
        self._assert_can_move(branch, allow_protected=allow_protected)
        self._revision_record(revision_id)
        previous = branch.head_revision_id
        moved = replace(branch, head_revision_id=revision_id)
        index = clone_index(index)
        index["branches"][moved.id] = moved.to_dict()
        event = self._event(
            index,
            branch_id=moved.id,
            result_revision_id=revision_id,
            actor_id=actor_id,
            base_revision_id=previous,
            payload={
                "kind": "branch_moved",
                "from_revision_id": previous,
                "to_revision_id": revision_id,
                "allow_protected": allow_protected,
            },
        )
        self._commit_with_event(index, event)
        return moved

    def set_branch_protection(
        self, branch_ref: str, *, protected: bool, actor_id: str
    ) -> Branch:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        branch = self._resolve_branch(index, branch_ref)
        updated = replace(branch, protected=protected)
        index = clone_index(index)
        index["branches"][updated.id] = updated.to_dict()
        event = self._event(
            index,
            branch_id=updated.id,
            result_revision_id=updated.head_revision_id,
            actor_id=actor_id,
            base_revision_id=updated.head_revision_id,
            payload={"kind": "branch_protection_changed", "protected": protected},
        )
        self._commit_with_event(index, event)
        return updated

    def archive_branch(self, branch_ref: str, *, actor_id: str) -> Branch:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        branch = self._resolve_branch(index, branch_ref)
        updated = replace(branch, archived=True)
        index = clone_index(index)
        index["branches"][updated.id] = updated.to_dict()
        event = self._event(
            index,
            branch_id=updated.id,
            result_revision_id=updated.head_revision_id,
            actor_id=actor_id,
            base_revision_id=updated.head_revision_id,
            payload={"kind": "branch_archived"},
        )
        self._commit_with_event(index, event)
        return updated

    def select_canonical_branch(self, branch_ref: str, *, actor_id: str) -> Branch:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        branch = self._resolve_branch(index, branch_ref)
        index = clone_index(index)
        index["canonical_branch_id"] = branch.id
        event = self._event(
            index,
            branch_id=branch.id,
            result_revision_id=branch.head_revision_id,
            actor_id=actor_id,
            base_revision_id=branch.head_revision_id,
            payload={"kind": "canonical_branch_selected"},
        )
        self._commit_with_event(index, event)
        return branch

    def create_checkpoint(
        self,
        name: str,
        *,
        actor_id: str,
        revision_id: str | None = None,
        branch_ref: str | None = None,
    ) -> Checkpoint:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        if name in index["checkpoints"]:
            raise CheckpointExistsError(f"checkpoint already exists and cannot be moved: {name}")
        if revision_id is not None:
            target = revision_id
            self._revision_record(target)
            branch = self._resolve_branch(index, branch_ref or str(index["canonical_branch_id"]))
        else:
            branch = self._resolve_branch(index, branch_ref or str(index["canonical_branch_id"]))
            target = branch.head_revision_id
        checkpoint = Checkpoint(
            id=f"chk_{new_ulid()}",
            name=name,
            revision_id=target,
            created_at=utc_now(),
            actor_id=actor_id,
            project_id=str(index["project_id"]),
        )
        index = clone_index(index)
        index["checkpoints"][name] = checkpoint.to_dict()
        event = self._event(
            index,
            branch_id=branch.id,
            result_revision_id=target,
            actor_id=actor_id,
            base_revision_id=target,
            payload={"kind": "checkpoint_created", "name": name, "checkpoint_id": checkpoint.id},
        )
        self._commit_with_event(index, event)
        return checkpoint

    def get_checkpoint(self, name: str) -> Checkpoint:
        index = self._ensure_index()
        raw = index["checkpoints"].get(name)
        if raw is None:
            raise RevisionNotFoundError(f"unknown checkpoint: {name}")
        return Checkpoint.from_dict(raw)

    def list_checkpoints(self) -> tuple[Checkpoint, ...]:
        index = self._ensure_index()
        checkpoints = [Checkpoint.from_dict(raw) for raw in index["checkpoints"].values()]
        return tuple(sorted(checkpoints, key=lambda checkpoint: checkpoint.name))

    def load_revision(self, revision_id: str) -> ScreenplayDocument:
        record = self._revision_record(revision_id)
        payload = json.loads(self.workspace.store.get_blob(record.blob_digest).decode("utf-8"))
        document = ScreenplayDocument.from_dict(payload)
        document.validate()
        return document

    def revision_blob_bytes(self, revision_id: str) -> bytes:
        record = self._revision_record(revision_id)
        return self.workspace.store.get_blob(record.blob_digest)

    def parent_chain(self, revision_id: str) -> tuple[RevisionRecord, ...]:
        chain: list[RevisionRecord] = []
        current: str | None = revision_id
        seen: set[str] = set()
        while current:
            if current in seen:
                raise RevisionError(f"revision parent cycle at {current}")
            seen.add(current)
            record = self._revision_record(current)
            chain.append(record)
            current = record.parent_revision_id
        return tuple(reversed(chain))

    def apply_change_set(
        self,
        change_set: ChangeSet,
        *,
        actor_id: str,
        branch_ref: str | None = None,
        device_id: str = DEFAULT_DEVICE_ID,
        allow_protected: bool = False,
    ) -> SaveAck:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        branch = self._resolve_branch(index, branch_ref or str(index["canonical_branch_id"]))
        self._assert_can_move(branch, allow_protected=allow_protected)
        if change_set.base_revision_id != branch.head_revision_id:
            raise StaleBaseError(
                "change set base_revision_id is not the current branch head; fail closed"
            )
        document = self.load_revision(branch.head_revision_id)
        ack = self._save_on_branch(
            document,
            branch_id=branch.id,
            actor_id=actor_id,
            device_id=device_id,
            change_set=change_set,
        )
        index = clone_index(self._load_required_index())
        index["branches"][branch.id] = replace(branch, head_revision_id=ack.revision_id).to_dict()
        event = self._event(
            index,
            branch_id=branch.id,
            result_revision_id=ack.revision_id,
            actor_id=actor_id,
            base_revision_id=change_set.base_revision_id,
            payload={
                "kind": "patch_accepted",
                "change_set": change_set.to_dict(),
                "blob_digest": ack.blob_digest,
            },
            operation_id=ack.operation_id,
        )
        self._commit_with_event(index, event)
        return ack

    def save_document(
        self,
        document: ScreenplayDocument,
        *,
        actor_id: str,
        branch_ref: str | None = None,
        device_id: str = DEFAULT_DEVICE_ID,
        allow_protected: bool = False,
    ) -> SaveAck:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        branch = self._resolve_branch(index, branch_ref or str(index["canonical_branch_id"]))
        self._assert_can_move(branch, allow_protected=allow_protected)
        parent = document.base_revision_id or branch.head_revision_id
        if parent != branch.head_revision_id:
            raise StaleBaseError("document base_revision_id is not the current branch head")
        ack = self._save_on_branch(
            document,
            branch_id=branch.id,
            actor_id=actor_id,
            device_id=device_id,
        )
        index = clone_index(self._load_required_index())
        index["branches"][branch.id] = replace(branch, head_revision_id=ack.revision_id).to_dict()
        event = self._event(
            index,
            branch_id=branch.id,
            result_revision_id=ack.revision_id,
            actor_id=actor_id,
            base_revision_id=parent,
            payload={"kind": "patch_accepted", "blob_digest": ack.blob_digest},
            operation_id=ack.operation_id,
        )
        self._commit_with_event(index, event)
        return ack

    def merge_into(
        self,
        *,
        source_branch: str,
        target_branch: str,
        actor_id: str,
        device_id: str = DEFAULT_DEVICE_ID,
        allow_protected: bool = False,
    ) -> Merge:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        source = self._resolve_branch(index, source_branch)
        target = self._resolve_branch(index, target_branch)
        base_id = self._common_ancestor(source.head_revision_id, target.head_revision_id)
        return self.three_way_merge(
            base_revision_id=base_id,
            source_revision_id=source.head_revision_id,
            target_revision_id=target.head_revision_id,
            actor_id=actor_id,
            branch_ref=target.id,
            device_id=device_id,
            allow_protected=allow_protected,
        )

    def three_way_merge(
        self,
        *,
        base_revision_id: str,
        source_revision_id: str,
        target_revision_id: str,
        actor_id: str,
        branch_ref: str | None = None,
        device_id: str = DEFAULT_DEVICE_ID,
        allow_protected: bool = False,
    ) -> Merge:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        branch = self._resolve_branch(index, branch_ref or str(index["canonical_branch_id"]))
        now = utc_now()
        base_doc = self.load_revision(base_revision_id)
        source_doc = self.load_revision(source_revision_id)
        target_doc = self.load_revision(target_revision_id)
        source_diff = diff_against_base(
            base_doc,
            source_doc,
            author_actor_id=actor_id,
            created_at=now,
            base_revision_id=base_revision_id,
        )
        target_diff = diff_against_base(
            base_doc,
            target_doc,
            author_actor_id=actor_id,
            created_at=now,
            base_revision_id=base_revision_id,
        )
        source_ops = effective_operations(source_diff, base_doc)
        target_ops = effective_operations(target_diff, base_doc)
        overlap = overlapping_targets(source_ops, target_ops)
        if overlap:
            conflicts = tuple(
                MergeConflict(
                    target_id=target_id,
                    reason="overlapping_operations",
                    source_operation_ids=tuple(
                        op.id for op in source_ops if target_id in operation_target_keys(op)
                    ),
                    target_operation_ids=tuple(
                        op.id for op in target_ops if target_id in operation_target_keys(op)
                    ),
                )
                for target_id in sorted(overlap)
            )
            merge = Merge(
                id=self._new_merge_id(),
                base_revision_id=base_revision_id,
                source_revision_id=source_revision_id,
                target_revision_id=target_revision_id,
                author_actor_id=actor_id,
                created_at=now,
                conflicts=conflicts,
                resolutions=(),
                resulting_revision_id=None,
                status="conflicted",
            )
            self._persist_merge(index, merge, branch_id=branch.id, actor_id=actor_id, kind="merge_conflicted")
            raise MergeConflictError(merge)

        composed = compose_operations(
            source_ops,
            target_ops,
            base_revision_id=base_revision_id,
            author_actor_id=actor_id,
            created_at=now,
        )
        try:
            merged_doc = try_apply(base_doc, composed)
        except InvalidOperationError:
            merge = Merge(
                id=self._new_merge_id(),
                base_revision_id=base_revision_id,
                source_revision_id=source_revision_id,
                target_revision_id=target_revision_id,
                author_actor_id=actor_id,
                created_at=now,
                conflicts=(
                    MergeConflict(
                        target_id=base_doc.id,
                        reason="apply_failed",
                    ),
                ),
                resulting_revision_id=None,
                status="conflicted",
            )
            self._persist_merge(index, merge, branch_id=branch.id, actor_id=actor_id, kind="merge_conflicted")
            raise MergeConflictError(merge) from None

        self._assert_can_move(branch, allow_protected=allow_protected)
        if branch.head_revision_id != target_revision_id:
            raise StaleBaseError("merge target is not the current branch head; fail closed")
        to_save = replace(merged_doc, base_revision_id=target_revision_id)
        ack = self._save_on_branch(
            to_save,
            branch_id=branch.id,
            actor_id=actor_id,
            device_id=device_id,
        )
        merge = Merge(
            id=self._new_merge_id(),
            base_revision_id=base_revision_id,
            source_revision_id=source_revision_id,
            target_revision_id=target_revision_id,
            author_actor_id=actor_id,
            created_at=now,
            conflicts=(),
            resolutions=(),
            resulting_revision_id=ack.revision_id,
            status="completed",
        )
        index = clone_index(self._load_required_index())
        index["branches"][branch.id] = replace(branch, head_revision_id=ack.revision_id).to_dict()
        self._persist_merge(
            index,
            merge,
            branch_id=branch.id,
            actor_id=actor_id,
            kind="merge_completed",
            extra_payload={"change_set": composed.to_dict(), "blob_digest": ack.blob_digest},
            base_revision_id=target_revision_id,
            result_revision_id=ack.revision_id,
        )
        return merge

    def resolve_merge(
        self,
        merge_id: str,
        *,
        actor_id: str,
        resolved_change_set: ChangeSet,
        branch_ref: str | None = None,
        device_id: str = DEFAULT_DEVICE_ID,
        allow_protected: bool = False,
        notes: str | None = None,
    ) -> Merge:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        original = self.get_merge(merge_id)
        if not original.conflicts:
            raise RevisionError("merge has no conflicts to resolve")
        branch = self._resolve_branch(index, branch_ref or str(index["canonical_branch_id"]))
        self._assert_can_move(branch, allow_protected=allow_protected)
        if resolved_change_set.base_revision_id != branch.head_revision_id:
            raise StaleBaseError("resolution change set is not based on current branch head")
        document = self.load_revision(branch.head_revision_id)
        ack = self._save_on_branch(
            document,
            branch_id=branch.id,
            actor_id=actor_id,
            device_id=device_id,
            change_set=resolved_change_set,
        )
        resolution = MergeResolution(
            id=f"mrs_{new_ulid()}",
            merge_id=original.id,
            actor_id=actor_id,
            created_at=utc_now(),
            resulting_revision_id=ack.revision_id,
            notes=notes,
        )
        resolved = Merge(
            id=self._new_merge_id(),
            base_revision_id=original.base_revision_id,
            source_revision_id=original.source_revision_id,
            target_revision_id=original.target_revision_id,
            author_actor_id=actor_id,
            created_at=resolution.created_at,
            conflicts=original.conflicts,
            resolutions=(resolution,),
            resulting_revision_id=ack.revision_id,
            status="resolved",
        )
        resolution_digest = put_json_blob(self.workspace, resolution.to_dict())
        index = clone_index(self._load_required_index())
        index["branches"][branch.id] = replace(branch, head_revision_id=ack.revision_id).to_dict()
        index["resolution_ids"] = [*index.get("resolution_ids", []), resolution.id]
        index["resolution_digests"] = {
            **index.get("resolution_digests", {}),
            resolution.id: resolution_digest,
        }
        self._persist_merge(
            index,
            resolved,
            branch_id=branch.id,
            actor_id=actor_id,
            kind="merge_completed",
            extra_payload={
                "resolved_from_merge_id": original.id,
                "change_set": resolved_change_set.to_dict(),
                "blob_digest": ack.blob_digest,
            },
            base_revision_id=resolved_change_set.base_revision_id,
            result_revision_id=ack.revision_id,
        )
        return resolved

    def get_merge(self, merge_id: str) -> Merge:
        index = self._ensure_index()
        digest = index.get("merge_digests", {}).get(merge_id)
        if digest is None:
            raise RevisionNotFoundError(f"unknown merge: {merge_id}")
        return Merge.from_dict(load_json_blob(self.workspace, str(digest)))

    def list_merges(self) -> tuple[Merge, ...]:
        index = self._ensure_index()
        merges = [self.get_merge(merge_id) for merge_id in index.get("merge_ids", [])]
        return tuple(merges)

    def store_proposal(self, proposal: Proposal) -> Proposal:
        if proposal.status is not ProposalStatus.PENDING:
            raise RevisionError("new proposals must be stored as pending")
        index = self._ensure_index(persist=True)
        if proposal.id in index.get("proposal_digests", {}):
            raise RevisionError(f"proposal already stored: {proposal.id}")
        digest = put_json_blob(self.workspace, proposal.to_dict())
        index = clone_index(index)
        index["proposal_ids"] = [*index["proposal_ids"], proposal.id]
        index["proposal_digests"][proposal.id] = digest
        index["proposal_status"][proposal.id] = ProposalStatus.PENDING.value
        commit_index(self.workspace, index)
        return proposal

    def get_proposal(self, proposal_id: str) -> Proposal:
        index = self._ensure_index()
        digest = index.get("proposal_digests", {}).get(proposal_id)
        if digest is None:
            raise RevisionNotFoundError(f"unknown proposal: {proposal_id}")
        stored = Proposal.from_dict(load_json_blob(self.workspace, str(digest)))
        status_value = index.get("proposal_status", {}).get(proposal_id, stored.status.value)
        status = ProposalStatus(status_value)
        revalidation = stored.revalidation
        superseded_by = index.get("proposal_superseded_by", {}).get(proposal_id)
        if superseded_by and revalidation is None:
            revalidation = stored.revalidation
        if status is stored.status:
            return stored
        return Proposal(
            id=stored.id,
            project_id=stored.project_id,
            change_set=stored.change_set,
            base_revision_id=stored.base_revision_id,
            intent=stored.intent,
            rationale_summary=stored.rationale_summary,
            provenance=stored.provenance,
            created_at=stored.created_at,
            status=status,
            impact=stored.impact,
            revalidation=revalidation,
            schema_version=stored.schema_version,
        )

    def proposal_blob_bytes(self, proposal_id: str) -> bytes:
        index = self._ensure_index()
        digest = index.get("proposal_digests", {}).get(proposal_id)
        if digest is None:
            raise RevisionNotFoundError(f"unknown proposal: {proposal_id}")
        return self.workspace.store.get_blob(str(digest))

    def list_proposals(self) -> tuple[Proposal, ...]:
        index = self._ensure_index()
        return tuple(self.get_proposal(proposal_id) for proposal_id in index.get("proposal_ids", []))

    def reject_proposal(self, proposal_id: str, *, actor_id: str) -> Proposal:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        proposal = self.get_proposal(proposal_id)
        if proposal.status is not ProposalStatus.PENDING:
            raise RevisionError("only pending proposals can be rejected")
        index = clone_index(index)
        index["proposal_status"][proposal_id] = ProposalStatus.REJECTED.value
        branch = self._resolve_branch(index, str(index["canonical_branch_id"]))
        event = self._event(
            index,
            branch_id=branch.id,
            result_revision_id=branch.head_revision_id,
            actor_id=actor_id,
            base_revision_id=proposal.base_revision_id,
            payload={"kind": "proposal_rejected", "proposal_id": proposal_id},
        )
        self._commit_with_event(index, event)
        return self.get_proposal(proposal_id)

    def accept_proposal(
        self,
        proposal_id: str,
        *,
        actor_id: str,
        branch_ref: str | None = None,
        device_id: str = DEFAULT_DEVICE_ID,
        allow_protected: bool = False,
    ) -> tuple[Proposal, SaveAck]:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        proposal = self.get_proposal(proposal_id)
        branch = self._resolve_branch(index, branch_ref or str(index["canonical_branch_id"]))
        if proposal.status is not ProposalStatus.PENDING:
            raise StaleProposalError("proposal is not pending; fail closed")
        if proposal.base_revision_id != branch.head_revision_id:
            raise StaleProposalError(
                "proposal base_revision_id is not the current branch head; fail closed"
            )
        ack = self.apply_change_set(
            proposal.change_set,
            actor_id=actor_id,
            branch_ref=branch.id,
            device_id=device_id,
            allow_protected=allow_protected,
        )
        index = clone_index(self._load_required_index())
        index["proposal_status"][proposal_id] = ProposalStatus.ACCEPTED.value
        branch = self._resolve_branch(index, branch.id)
        event = self._event(
            index,
            branch_id=branch.id,
            result_revision_id=ack.revision_id,
            actor_id=actor_id,
            base_revision_id=proposal.base_revision_id,
            payload={
                "kind": "proposal_accepted",
                "proposal_id": proposal_id,
                "change_set": proposal.change_set.to_dict(),
            },
            operation_id=ack.operation_id,
        )
        self._commit_with_event(index, event)
        return self.get_proposal(proposal_id), ack

    def rebase_proposal(
        self,
        proposal_id: str,
        *,
        actor_id: str,
        branch_ref: str | None = None,
    ) -> Proposal:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        proposal = self.get_proposal(proposal_id)
        branch = self._resolve_branch(index, branch_ref or str(index["canonical_branch_id"]))
        if proposal.status is not ProposalStatus.PENDING:
            raise StaleProposalError("only pending proposals can be rebased")
        if proposal.base_revision_id == branch.head_revision_id:
            return proposal
        now = utc_now()
        base_doc = self.load_revision(proposal.base_revision_id)
        head_doc = self.load_revision(branch.head_revision_id)
        source_doc = try_apply(base_doc, proposal.change_set)
        source_diff = diff_against_base(
            base_doc,
            source_doc,
            author_actor_id=actor_id,
            created_at=now,
            base_revision_id=proposal.base_revision_id,
        )
        target_diff = diff_against_base(
            base_doc,
            head_doc,
            author_actor_id=actor_id,
            created_at=now,
            base_revision_id=proposal.base_revision_id,
        )
        source_ops = effective_operations(source_diff, base_doc)
        target_ops = effective_operations(target_diff, base_doc)
        if overlapping_targets(source_ops, target_ops):
            index = clone_index(index)
            index["proposal_status"][proposal_id] = ProposalStatus.STALE.value
            event = self._event(
                index,
                branch_id=branch.id,
                result_revision_id=branch.head_revision_id,
                actor_id=actor_id,
                base_revision_id=proposal.base_revision_id,
                payload={"kind": "proposal_stale", "proposal_id": proposal_id},
            )
            self._commit_with_event(index, event)
            raise RebaseError("proposal rebase overlaps current head; fail closed")
        rebased_ops = tuple(
            copy_operation(operation, order=order) for order, operation in enumerate(source_ops)
        )
        new_change_set = ChangeSet(
            id=new_id("change_set"),
            base_revision_id=branch.head_revision_id,
            author_actor_id=actor_id,
            created_at=now,
            operations=rebased_ops,
        )
        try:
            try_apply(head_doc, new_change_set)
        except InvalidOperationError as exc:
            index = clone_index(index)
            index["proposal_status"][proposal_id] = ProposalStatus.STALE.value
            event = self._event(
                index,
                branch_id=branch.id,
                result_revision_id=branch.head_revision_id,
                actor_id=actor_id,
                base_revision_id=proposal.base_revision_id,
                payload={"kind": "proposal_stale", "proposal_id": proposal_id, "reason": str(exc)},
            )
            self._commit_with_event(index, event)
            raise RebaseError("proposal rebase cannot apply cleanly; fail closed") from exc
        new_proposal = Proposal(
            id=new_id("proposal"),
            project_id=proposal.project_id,
            change_set=new_change_set,
            base_revision_id=branch.head_revision_id,
            intent=proposal.intent,
            rationale_summary=proposal.rationale_summary,
            provenance=proposal.provenance,
            created_at=now,
            status=ProposalStatus.PENDING,
            impact=proposal.impact,
            revalidation=RevalidationRecord(
                checked_at=now,
                base_revision_id=branch.head_revision_id,
                is_current=True,
                notes=f"rebased from {proposal.id}",
            ),
        )
        digest = put_json_blob(self.workspace, new_proposal.to_dict())
        index = clone_index(self._load_required_index())
        index["proposal_ids"] = [*index["proposal_ids"], new_proposal.id]
        index["proposal_digests"][new_proposal.id] = digest
        index["proposal_status"][new_proposal.id] = ProposalStatus.PENDING.value
        index["proposal_status"][proposal.id] = ProposalStatus.SUPERSEDED.value
        index["proposal_superseded_by"][proposal.id] = new_proposal.id
        event = self._event(
            index,
            branch_id=branch.id,
            result_revision_id=branch.head_revision_id,
            actor_id=actor_id,
            base_revision_id=branch.head_revision_id,
            payload={
                "kind": "proposal_rebased",
                "old_proposal_id": proposal.id,
                "new_proposal_id": new_proposal.id,
            },
        )
        self._commit_with_event(index, event)
        return new_proposal

    def restore(
        self,
        *,
        actor_id: str,
        checkpoint_name: str | None = None,
        revision_id: str | None = None,
        branch_ref: str | None = None,
        device_id: str = DEFAULT_DEVICE_ID,
        allow_protected: bool = False,
    ) -> SaveAck:
        index = self._ensure_index(actor_id=actor_id, persist=True)
        branch = self._resolve_branch(index, branch_ref or str(index["canonical_branch_id"]))
        self._assert_can_move(branch, allow_protected=allow_protected)
        if checkpoint_name is not None:
            snapshot_id = self.get_checkpoint(checkpoint_name).revision_id
        elif revision_id is not None:
            snapshot_id = revision_id
        else:
            raise RevisionError("restore requires checkpoint_name or revision_id")
        abandoned = branch.head_revision_id
        snapshot = self.load_revision(snapshot_id)
        to_save = replace(snapshot, base_revision_id=abandoned)
        ack = self._save_on_branch(
            to_save,
            branch_id=branch.id,
            actor_id=actor_id,
            device_id=device_id,
        )
        index = clone_index(self._load_required_index())
        index["branches"][branch.id] = replace(branch, head_revision_id=ack.revision_id).to_dict()
        event = self._event(
            index,
            branch_id=branch.id,
            result_revision_id=ack.revision_id,
            actor_id=actor_id,
            base_revision_id=abandoned,
            payload={
                "kind": "restore_completed",
                "restored_from_revision_id": snapshot_id,
                "checkpoint_name": checkpoint_name,
                "abandoned_head_revision_id": abandoned,
            },
            operation_id=ack.operation_id,
        )
        self._commit_with_event(index, event)
        return ack

    def list_events(self, *, branch_id: str | None = None) -> tuple[ProjectEvent, ...]:
        index = self._ensure_index()
        events: list[ProjectEvent] = []
        for event_id in index.get("event_ids", []):
            digest = index["event_digests"][event_id]
            event = ProjectEvent.from_dict(load_json_blob(self.workspace, str(digest)))
            if branch_id is None or event.branch_id == branch_id:
                events.append(event)
        return tuple(events)

    def event_blob_bytes(self, event_id: str) -> bytes:
        index = self._ensure_index()
        digest = index.get("event_digests", {}).get(event_id)
        if digest is None:
            raise RevisionNotFoundError(f"unknown event: {event_id}")
        return self.workspace.store.get_blob(str(digest))

    def replay_head(self, branch_ref: str | None = None) -> ScreenplayDocument:
        index = self._ensure_index()
        branch = self._resolve_branch(index, branch_ref or str(index["canonical_branch_id"]))
        replayed_head: str | None = None
        for event in self.list_events():
            payload = _payload(event)
            self._assert_event_integrity(event)
            if event.branch_id != branch.id:
                continue
            kind = payload.get("kind")
            if kind in MUTATING_KINDS or kind in {"branch_moved", "branch_created"}:
                replayed_head = event.result_revision_id
            if (
                kind in {"patch_accepted", "proposal_accepted"}
                and isinstance(payload.get("change_set"), dict)
                and event.base_revision_id
            ):
                base = self.load_revision(event.base_revision_id)
                applied = apply_change_set(base, ChangeSet.from_dict(payload["change_set"]))
                result = self.load_revision(event.result_revision_id)
                if not content_equal(applied, result):
                    raise ReplayError("replayed change set does not match stored revision blob")
        if replayed_head is None:
            replayed_head = branch.head_revision_id
        if replayed_head != branch.head_revision_id:
            raise ReplayError("replayed head revision does not match stored branch head")
        stored = self.load_revision(branch.head_revision_id)
        if stored.base_revision_id != branch.head_revision_id:
            raise ReplayError("stored head blob is not content-addressed to the head revision")
        return stored

    def history_projection(self, branch_ref: str | None = None) -> HistoryProjection:
        index = self._ensure_index()
        branch = self._resolve_branch(index, branch_ref or str(index["canonical_branch_id"]))
        events = self.list_events()
        events_by_revision: dict[str, list[str]] = {}
        for event in events:
            events_by_revision.setdefault(event.result_revision_id, []).append(event.id)
        checkpoints_by_revision: dict[str, list[str]] = {}
        for checkpoint in self.list_checkpoints():
            checkpoints_by_revision.setdefault(checkpoint.revision_id, []).append(checkpoint.name)
        branches_by_revision: dict[str, list[str]] = {}
        for listed in self.list_branches():
            branches_by_revision.setdefault(listed.head_revision_id, []).append(listed.name)
        records: list[HistoryRecord] = []
        for record in self.parent_chain(branch.head_revision_id):
            records.append(
                HistoryRecord(
                    revision_id=record.id,
                    parent_revision_id=record.parent_revision_id,
                    actor_id=record.actor_id,
                    timestamp=record.created_at,
                    event_ids=tuple(events_by_revision.get(record.id, ())),
                    checkpoint_names=tuple(sorted(checkpoints_by_revision.get(record.id, ()))),
                    branch_names=tuple(sorted(branches_by_revision.get(record.id, ()))),
                )
            )
        return HistoryProjection(
            branch_id=branch.id,
            branch_name=branch.name,
            head_revision_id=branch.head_revision_id,
            records=tuple(records),
        )

    def diff_projection(
        self,
        from_revision_id: str,
        to_revision_id: str,
        *,
        actor_id: str,
    ) -> DiffProjection:
        source = self.load_revision(from_revision_id)
        target = self.load_revision(to_revision_id)
        created_at = self._revision_record(to_revision_id).created_at
        volatile = structural_diff(
            snapshot_for_diff(source),
            snapshot_for_diff(target),
            author_actor_id=actor_id,
            created_at=created_at,
            base_revision_id=from_revision_id,
        )
        change_set = stabilize_diff_change_set(
            volatile,
            from_revision_id=from_revision_id,
            to_revision_id=to_revision_id,
            created_at=created_at,
        )
        return DiffProjection(
            from_revision_id=from_revision_id,
            to_revision_id=to_revision_id,
            change_set=change_set,
            operations_text=render_diff_text(change_set),
        )

    def render_history_text(self, branch_ref: str | None = None) -> str:
        return render_history_text(self.history_projection(branch_ref))

    def render_history_html(self, branch_ref: str | None = None) -> str:
        return render_history_html(self.history_projection(branch_ref))

    def export_document(self, destination: Path, document_id: str | None = None) -> Path:
        return self.workspace.export_document(destination, document_id)

    def _save_on_branch(
        self,
        document: ScreenplayDocument,
        *,
        branch_id: str,
        actor_id: str,
        device_id: str,
        change_set: ChangeSet | None = None,
    ) -> SaveAck:
        self.workspace.store.set_meta("active_branch_id", branch_id)
        return self.workspace.save(
            document, actor_id=actor_id, device_id=device_id, change_set=change_set
        )

    def _ensure_index(self, *, actor_id: str | None = None, persist: bool = False) -> dict[str, Any]:
        loaded = load_index(self.workspace)
        if loaded is not None and loaded.get("branches"):
            return loaded
        bootstrapped = self._bootstrap_index(actor_id=actor_id)
        if persist or loaded is None:
            commit_index(self.workspace, bootstrapped)
        return bootstrapped

    def _load_required_index(self) -> dict[str, Any]:
        loaded = load_index(self.workspace)
        if loaded is None:
            raise RevisionError("revisions index is missing")
        return loaded

    def _bootstrap_index(self, *, actor_id: str | None = None) -> dict[str, Any]:
        project_id = self.workspace.store.get_meta("active_project_id")
        document_id = self.workspace.store.get_meta("active_document_id")
        branch_id = self.workspace.store.get_meta("active_branch_id")
        if project_id is None or document_id is None or branch_id is None:
            raise RevisionError("workspace has no active project/document/branch")
        head = self.workspace.head_revision_id(document_id)
        if head is None:
            raise RevisionError("workspace document has no head revision")
        record = self._revision_record(head)
        created = record.created_at
        owner = actor_id or record.actor_id
        index = empty_index(
            project_id=project_id, document_id=document_id, canonical_branch_id=branch_id
        )
        branch = Branch(
            id=branch_id,
            name=DEFAULT_BRANCH_NAME,
            head_revision_id=head,
            project_id=project_id,
            created_at=created,
            protected=False,
            archived=False,
        )
        index["branches"][branch.id] = branch.to_dict()
        index["branch_names"][branch.name] = branch.id
        event = make_project_event(
            project_id=project_id,
            branch_id=branch.id,
            result_revision_id=head,
            actor_id=owner,
            base_revision_id=head,
            payload={"kind": "branch_created", "name": branch.name, "bootstrap": True},
        )
        digest = put_json_blob(self.workspace, event.to_dict())
        index["event_ids"] = [event.id]
        index["event_digests"] = {event.id: digest}
        return index

    def _resolve_branch(self, index: dict[str, Any], branch_ref: str) -> Branch:
        branch_id = branch_ref
        if branch_ref in index.get("branch_names", {}):
            branch_id = str(index["branch_names"][branch_ref])
        raw = index.get("branches", {}).get(branch_id)
        if raw is None:
            raise RevisionNotFoundError(f"unknown branch: {branch_ref}")
        return Branch.from_dict(raw)

    def _branch_from_index(self, index: dict[str, Any], branch_id: str) -> Branch:
        return self._resolve_branch(index, branch_id)

    def _assert_can_move(self, branch: Branch, *, allow_protected: bool) -> None:
        if branch.archived:
            raise ArchivedBranchError(f"archived branch cannot move: {branch.name}")
        if branch.protected and not allow_protected:
            raise ProtectedBranchError(
                f"protected branch {branch.name} refuses silent movement; pass allow_protected=True"
            )

    def _revision_record(self, revision_id: str) -> RevisionRecord:
        row = self.workspace.store.fetchone(
            "SELECT id, project_id, document_id, branch_id, parent_revision_id, "
            "blob_digest, created_at, actor_id FROM revisions WHERE id=?",
            (revision_id,),
        )
        if row is None:
            raise RevisionNotFoundError(f"unknown revision: {revision_id}")
        parent = row["parent_revision_id"]
        return RevisionRecord(
            id=str(row["id"]),
            parent_revision_id=str(parent) if parent is not None else None,
            blob_digest=str(row["blob_digest"]),
            created_at=str(row["created_at"]),
            actor_id=str(row["actor_id"]),
            branch_id=str(row["branch_id"]),
            project_id=str(row["project_id"]),
            document_id=str(row["document_id"]),
        )

    def _common_ancestor(self, left_id: str, right_id: str) -> str:
        left_ids = {record.id for record in self.parent_chain(left_id)}
        for record in reversed(self.parent_chain(right_id)):
            if record.id in left_ids:
                return record.id
        raise RevisionError("no common ancestor for three-way merge")

    def _event(
        self,
        index: dict[str, Any],
        *,
        branch_id: str,
        result_revision_id: str,
        actor_id: str,
        payload: dict[str, Any],
        base_revision_id: str | None = None,
        operation_id: str | None = None,
    ) -> ProjectEvent:
        return make_project_event(
            project_id=str(index["project_id"]),
            branch_id=branch_id,
            result_revision_id=result_revision_id,
            actor_id=actor_id,
            payload=payload,
            base_revision_id=base_revision_id,
            operation_id=operation_id,
        )

    def _commit_with_event(self, index: dict[str, Any], event: ProjectEvent) -> None:
        digest = put_json_blob(self.workspace, event.to_dict())
        index["event_ids"] = [*index.get("event_ids", []), event.id]
        index["event_digests"] = {**index.get("event_digests", {}), event.id: digest}
        commit_index(self.workspace, index)

    def _persist_merge(
        self,
        index: dict[str, Any],
        merge: Merge,
        *,
        branch_id: str,
        actor_id: str,
        kind: str,
        extra_payload: dict[str, Any] | None = None,
        base_revision_id: str | None = None,
        result_revision_id: str | None = None,
    ) -> None:
        digest = put_json_blob(self.workspace, merge.to_dict())
        index = clone_index(index)
        index["merge_ids"] = [*index.get("merge_ids", []), merge.id]
        index["merge_digests"] = {**index.get("merge_digests", {}), merge.id: digest}
        payload: dict[str, Any] = {
            "kind": kind,
            "merge_id": merge.id,
            "base_revision_id": merge.base_revision_id,
            "source_revision_id": merge.source_revision_id,
            "target_revision_id": merge.target_revision_id,
            "conflict_count": len(merge.conflicts),
        }
        if extra_payload:
            payload.update(extra_payload)
        event = self._event(
            index,
            branch_id=branch_id,
            result_revision_id=result_revision_id or merge.resulting_revision_id or merge.target_revision_id,
            actor_id=actor_id,
            base_revision_id=base_revision_id or merge.target_revision_id,
            payload=payload,
        )
        self._commit_with_event(index, event)

    def _assert_event_integrity(self, event: ProjectEvent) -> None:
        expected = compute_integrity_hash(
            project_id=event.project_id,
            branch_id=event.branch_id,
            base_revision_id=event.base_revision_id,
            result_revision_id=event.result_revision_id,
            actor_id=event.actor_id,
            effective_principal_id=event.effective_principal_id,
            command_id=event.command_id,
            operation_id=event.operation_id,
            event_type=event.event_type,
            schema_version=event.schema_version,
            causal_id=event.causal_id,
            correlation_id=event.correlation_id,
            payload=_payload(event),
        )
        if expected != event.integrity_hash:
            raise ReplayError("event integrity_hash does not match recomputation")

    def _new_branch_id(self) -> str:
        return new_id("branch")

    def _new_merge_id(self) -> str:
        return f"mrg_{new_ulid()}"


def _payload(event: ProjectEvent) -> dict[str, Any]:
    raw = to_json_dict(event.payload) if event.payload is not None else {}
    return raw if isinstance(raw, dict) else {}
