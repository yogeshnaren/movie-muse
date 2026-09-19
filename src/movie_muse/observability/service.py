"""Structured traces and metrics without content leakage."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from movie_muse.audit.api import AuditLog, PolicyDecision
from movie_muse.authorization.api import Action, AuthorizationService, Resource, ResourceKind
from movie_muse.identity.api import Principal
from movie_muse.observability.errors import ContentLeakageError, ObservabilityError, SloBreachError
from movie_muse.observability.index import load_index, load_payload, mutate_index, put_payload
from movie_muse.observability.types import (
    FORBIDDEN_ATTRIBUTE_KEYS,
    REDACTION_MARK,
    MetricSample,
    SloDefinition,
    TraceRecord,
)
from movie_muse.persistence.api import LocalWorkspace, utc_now
from movie_muse.schemas.api import new_ulid

DEFAULT_SLOS: tuple[SloDefinition, ...] = (
    SloDefinition(name="availability", target=0.999, kind="ratio"),
    SloDefinition(name="latency_ms_p99", target=2000.0, kind="budget"),
)


def redact_attributes(attributes: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in attributes.items():
        lowered = str(key).lower()
        if lowered in FORBIDDEN_ATTRIBUTE_KEYS or any(
            token in lowered for token in ("password", "secret", "token", "prompt")
        ):
            redacted[str(key)] = REDACTION_MARK
        elif isinstance(value, Mapping):
            redacted[str(key)] = redact_attributes(value)
        else:
            redacted[str(key)] = value
    return redacted


def _assert_no_leak(payload: Mapping[str, Any]) -> None:
    serialized = str(payload).lower()
    if REDACTION_MARK.lower() in serialized:
        serialized = serialized.replace(REDACTION_MARK.lower(), "")
    for needle in ("int. ", "ext. ", "ignore previous", "api_key=", "bearer "):
        if needle in serialized:
            raise ContentLeakageError("telemetry must not carry screenplay or secret content")


class ObservabilityService:
    """Local traces/metrics. Content-bearing keys are redacted before persist."""

    def __init__(
        self,
        workspace: LocalWorkspace,
        authorization: AuthorizationService,
        audit: AuditLog,
        *,
        organization_id: str,
        project_id: str,
    ) -> None:
        self.workspace = workspace
        self.authorization = authorization
        self.audit = audit
        self.organization_id = organization_id
        self.project_id = project_id

    def _resource(self) -> Resource:
        return Resource(
            kind=ResourceKind.PROJECT,
            id=self.project_id,
            organization_id=self.organization_id,
            project_id=self.project_id,
        )

    def emit_trace(
        self,
        operation: str,
        *,
        principal: Principal,
        acl_epoch: int,
        attributes: Mapping[str, Any] | None = None,
    ) -> TraceRecord:
        self.authorization.require(principal, Action.READ, self._resource(), acl_epoch=acl_epoch)
        cleaned = redact_attributes(attributes or {})
        _assert_no_leak(cleaned)
        record = TraceRecord(
            id=f"trc_{new_ulid()}",
            operation=operation.strip(),
            attributes=cleaned,
            recorded_at=utc_now(),
        )
        digest = put_payload(self.workspace, record.to_dict())

        def persist(index: dict[str, Any]) -> None:
            ids = list(index.get("trace_ids", []))
            ids.append(record.id)
            index["trace_ids"] = ids
            digests = dict(index.get("trace_digests", {}))
            digests[record.id] = digest
            index["trace_digests"] = digests

        mutate_index(self.workspace, persist)
        self.audit.append(
            actor_id=principal.actor_id,
            effective_principal_id=principal.actor_id,
            operation="observability.trace",
            object_kind="trace",
            object_id=record.id,
            policy_decision=PolicyDecision.ALLOW,
            acl_epoch=acl_epoch,
            reason=operation,
        )
        return record

    def emit_metric(
        self,
        name: str,
        value: float,
        *,
        principal: Principal,
        acl_epoch: int,
        labels: Mapping[str, str] | None = None,
    ) -> MetricSample:
        self.authorization.require(principal, Action.READ, self._resource(), acl_epoch=acl_epoch)
        cleaned = {str(key): str(item) for key, item in redact_attributes(labels or {}).items()}
        _assert_no_leak(cleaned)
        sample = MetricSample(
            name=name.strip(),
            value=float(value),
            labels=cleaned,
            recorded_at=utc_now(),
        )

        def persist(index: dict[str, Any]) -> None:
            metrics = list(index.get("metrics", []))
            metrics.append(sample.to_dict())
            index["metrics"] = metrics

        mutate_index(self.workspace, persist)
        return sample

    def record_slo_sample(
        self,
        name: str,
        *,
        success: bool,
        latency_ms: float,
        principal: Principal,
        acl_epoch: int,
    ) -> None:
        self.authorization.require(principal, Action.READ, self._resource(), acl_epoch=acl_epoch)

        def persist(index: dict[str, Any]) -> None:
            samples = dict(index.get("slo_samples", {}))
            current = dict(samples.get(name, {"success": 0, "total": 0, "latencies": []}))
            current["total"] = int(current.get("total", 0)) + 1
            current["success"] = int(current.get("success", 0)) + (1 if success else 0)
            latencies = list(current.get("latencies", []))
            latencies.append(float(latency_ms))
            current["latencies"] = latencies[-128:]
            samples[name] = current
            index["slo_samples"] = samples

        mutate_index(self.workspace, persist)

    def list_traces(self) -> tuple[TraceRecord, ...]:
        index = load_index(self.workspace)
        items: list[TraceRecord] = []
        for trace_id in index.get("trace_ids", []):
            digest = dict(index.get("trace_digests", {})).get(str(trace_id))
            if digest:
                items.append(TraceRecord.from_dict(load_payload(self.workspace, str(digest))))
        return tuple(items)

    def list_metrics(self) -> tuple[MetricSample, ...]:
        index = load_index(self.workspace)
        return tuple(MetricSample.from_dict(dict(item)) for item in index.get("metrics", []))

    def assert_slo(self, name: str) -> None:
        definition = next((item for item in DEFAULT_SLOS if item.name == name), None)
        if definition is None:
            raise ObservabilityError(f"unknown slo: {name}")
        index = load_index(self.workspace)
        sample = dict(dict(index.get("slo_samples", {})).get(name, {}))
        total = int(sample.get("total", 0))
        if total <= 0:
            raise SloBreachError(f"{name} has no samples")
        if definition.kind == "ratio":
            ratio = int(sample.get("success", 0)) / total
            if ratio < definition.target:
                raise SloBreachError(f"{name} {ratio:.4f} is below {definition.target}")
            return
        latencies = sorted(float(item) for item in sample.get("latencies", []))
        index_p99 = max(0, int(round(0.99 * (len(latencies) - 1))))
        p99 = latencies[index_p99]
        if p99 > definition.target:
            raise SloBreachError(f"{name} p99 {p99} exceeds {definition.target}")
