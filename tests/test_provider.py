import json

import httpx
import pytest

from agentlab.core.models import CompletionRequest, Message, ModelConfig
from agentlab.core.traces import Recorder
from agentlab.providers.openai import OpenAIProvider
from agentlab.providers.session import ModelSession, ProviderError


def test_http_adapter_preserves_tools_usage_and_model_version(monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret-test-token")

    def handler(request):
        payload = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer secret-test-token"
        assert payload["messages"] == [{"role": "user", "content": "Calculate"}]
        return httpx.Response(
            200,
            json={
                "model": "pinned-model",
                "id": "response-1",
                "system_fingerprint": "fp1",
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "reasoning_content": "NEVER STORE THIS",
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {
                                        "name": "calculator",
                                        "arguments": '{"expression":"2+2"}',
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    config = ModelConfig(
        provider="openai",
        model="requested",
        api_key_env="TEST_KEY",
        input_usd_per_million=1,
        output_usd_per_million=2,
    )
    provider = OpenAIProvider(config, transport=httpx.MockTransport(handler))
    result = provider.complete(
        CompletionRequest(messages=[Message(role="user", content="Calculate")])
    )
    assert result.model == "pinned-model"
    assert result.message.tool_calls[0].arguments == {"expression": "2+2"}
    assert result.usage.cost_usd == pytest.approx(0.00014)
    assert "NEVER STORE THIS" not in result.model_dump_json()


def test_retries_are_recorded_and_error_body_cannot_leak_key(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_KEY", "do-not-log-secret")
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, text="do-not-log-secret")
        return httpx.Response(
            200,
            json={
                "model": "test",
                "choices": [
                    {"message": {"role": "assistant", "content": "done"}, "finish_reason": "stop"}
                ],
            },
        )

    config = ModelConfig(provider="openai", model="test", api_key_env="TEST_KEY")
    recorder = Recorder("run", tmp_path / "trace.jsonl")
    session = ModelSession(
        OpenAIProvider(config, transport=httpx.MockTransport(handler)), config, recorder, 1
    )
    result = session.call([Message(role="user", content="Hello")], purpose="answer")
    assert result.message.content == "done"
    assert result.usage.input_tokens is None
    assert [e.type for e in recorder.events].count("model_call") == 2
    assert any(e.type == "retry" for e in recorder.events)
    assert "do-not-log-secret" not in recorder.path.read_text()


def test_missing_credentials_fail_without_http_request(monkeypatch):
    monkeypatch.delenv("MISSING_KEY", raising=False)
    provider = OpenAIProvider(ModelConfig(provider="openai", api_key_env="MISSING_KEY"))
    with pytest.raises(ProviderError, match="MISSING_KEY"):
        provider.complete(CompletionRequest(messages=[Message(role="user", content="hi")]))
