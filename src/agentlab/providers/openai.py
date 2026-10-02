"""OpenAI-compatible Chat Completions over HTTP; no SDK state or hidden retries."""

import json
import os

import httpx

from agentlab.core.models import (
    Completion,
    CompletionRequest,
    Message,
    ModelConfig,
    ToolCall,
    Usage,
)
from agentlab.providers.session import ProviderError


class OpenAIProvider:
    def __init__(self, config: ModelConfig, *, transport: httpx.BaseTransport | None = None):
        self.config = config
        self.transport = transport

    def complete(self, request: CompletionRequest) -> Completion:
        key = os.getenv(self.config.api_key_env)
        if not key:
            raise ProviderError(f"Set {self.config.api_key_env} before using the openai provider")
        messages = []
        for message in request.messages:
            item = {"role": message.role, "content": message.content}
            if message.tool_call_id:
                item["tool_call_id"] = message.tool_call_id
            if message.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                    }
                    for call in message.tool_calls
                ]
            messages.append(item)
        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_completion_tokens": self.config.max_output_tokens,
            "seed": request.seed,
        }
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if request.json_output:
            payload["response_format"] = {"type": "json_object"}
        if request.tools:
            payload["tools"] = [
                {"type": "function", "function": t.model_dump()} for t in request.tools
            ]
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=self.config.timeout_seconds,
                follow_redirects=False,
            ) as client:
                response = client.post(
                    self.config.base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json=payload,
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderError(
                f"Provider transport failure ({type(exc).__name__})", retryable=True
            ) from exc
        if response.status_code != 200:
            raise ProviderError(
                f"Provider HTTP {response.status_code}",
                retryable=response.status_code == 429 or response.status_code >= 500,
            )
        observed = None
        try:
            data = response.json()
            choice = data["choices"][0]
            msg = choice["message"]
            usage_data = data.get("usage") or {}
            usage = Usage(
                input_tokens=usage_data.get("prompt_tokens"),
                output_tokens=usage_data.get("completion_tokens"),
            )
            if (
                usage.input_tokens is not None
                and usage.output_tokens is not None
                and self.config.input_usd_per_million is not None
                and self.config.output_usd_per_million is not None
            ):
                usage.cost_usd = (
                    usage.input_tokens * self.config.input_usd_per_million
                    + usage.output_tokens * self.config.output_usd_per_million
                ) / 1e6
                usage.cost_source = (
                    "estimate: configured per-million-token rates; no cache discounts"
                )
            observed = {
                "model": data.get("model"),
                "provider": "openai",
                "usage": usage.model_dump(),
                "message": {
                    "role": "assistant",
                    "content": msg.get("content") if isinstance(msg.get("content"), str) else None,
                    "raw_tool_calls": [
                        {
                            "id": c.get("id"),
                            "name": c.get("function", {}).get("name"),
                            "arguments": c.get("function", {}).get("arguments"),
                        }
                        for c in msg.get("tool_calls") or []
                        if isinstance(c, dict) and isinstance(c.get("function"), dict)
                    ],
                },
                "metadata": {
                    "id": data.get("id"),
                    "fingerprint": data.get("system_fingerprint"),
                    "finish_reason": choice.get("finish_reason"),
                },
            }
            calls = [
                ToolCall(
                    id=c["id"],
                    name=c["function"]["name"],
                    arguments=json.loads(c["function"]["arguments"]),
                )
                for c in msg.get("tool_calls") or []
            ]
            # Explicit allowlist deliberately excludes provider-private reasoning fields.
            return Completion(
                message=Message(role="assistant", content=msg.get("content"), tool_calls=calls),
                model=data["model"],
                provider="openai",
                usage=usage,
                metadata={
                    "id": data.get("id"),
                    "fingerprint": data.get("system_fingerprint"),
                    "finish_reason": choice.get("finish_reason"),
                    "refusal": msg.get("refusal"),
                },
            )
        except (KeyError, IndexError, TypeError, ValueError, RecursionError) as exc:
            raise ProviderError(
                f"Invalid provider response ({type(exc).__name__})", observed_response=observed
            ) from exc
