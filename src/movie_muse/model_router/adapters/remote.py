"""Generic HTTP remote adapter. No vendor provider SDKs."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any, Protocol

from movie_muse.model_router.errors import ProviderUnavailableError
from movie_muse.model_router.types import AdapterResult, ModelRequest, RoutingDecision

REMOTE_BASE_URL_ENV = "MOVIE_MUSE_REMOTE_MODEL_BASE_URL"
REMOTE_API_KEY_ENV = "MOVIE_MUSE_REMOTE_MODEL_API_KEY"


class HttpClient(Protocol):
    def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_s: float,
    ) -> Mapping[str, Any]: ...


class UrllibHttpClient:
    def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout_s: float,
    ) -> Mapping[str, Any]:
        body = json.dumps(dict(payload), sort_keys=True).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", **dict(headers)},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise ProviderUnavailableError(f"remote provider unreachable: {exc}") from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderUnavailableError("remote provider returned non-JSON") from exc
        if not isinstance(parsed, dict):
            raise ProviderUnavailableError("remote provider returned a non-object")
        return parsed


def remote_base_url(env_name: str = REMOTE_BASE_URL_ENV) -> str | None:
    value = os.environ.get(env_name, "").strip()
    return value or None


class RemoteProviderAdapter:
    def __init__(
        self,
        *,
        base_url_env: str = REMOTE_BASE_URL_ENV,
        api_key_env: str = REMOTE_API_KEY_ENV,
        http_client: HttpClient | None = None,
        timeout_s: float = 20.0,
    ) -> None:
        self.base_url_env = base_url_env
        self.api_key_env = api_key_env
        self.http_client = http_client or UrllibHttpClient()
        self.timeout_s = timeout_s

    def invoke(
        self,
        request: ModelRequest,
        decision: RoutingDecision,
        prompt_template: str,
    ) -> AdapterResult:
        base = remote_base_url(self.base_url_env)
        if not base:
            raise ProviderUnavailableError(
                f"remote provider unavailable ({self.base_url_env} is unset)"
            )
        url = f"{base.rstrip('/')}/invoke"
        headers: dict[str, str] = {}
        api_key = os.environ.get(self.api_key_env, "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": decision.model,
            "capability": request.capability,
            "input": request.input_mapping(),
            "prompt_template": prompt_template,
            "structured_output": request.structured_output
            if not isinstance(request.structured_output, bool)
            else request.structured_output,
        }
        response = self.http_client.post_json(url, payload, headers, self.timeout_s)
        output_raw = response.get("output")
        if not isinstance(output_raw, dict):
            raise ProviderUnavailableError("remote provider omitted object output")
        usage_raw = response.get("usage")
        usage: dict[str, Any] = dict(usage_raw) if isinstance(usage_raw, dict) else {}
        model_version = str(response.get("model_version") or decision.model_version)
        return AdapterResult(
            output=dict(output_raw),
            model_version=model_version,
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            actual_cost=float(usage.get("cost") or decision.estimated_cost),
            method=str(output_raw.get("method") or "remote_http"),
            assumptions=tuple(str(item) for item in output_raw.get("assumptions") or ("remote",)),
            uncertainty=str(output_raw.get("uncertainty") or "provider_reported"),
        )
