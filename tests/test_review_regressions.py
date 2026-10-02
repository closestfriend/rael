import httpx
import pytest
from test_pipeline import tiny_config

from agentlab.core.evaluators import objective_grade
from agentlab.core.experiments import run_experiment
from agentlab.core.metrics import run_metrics
from agentlab.core.models import Completion, Message, ModelConfig, Run, Task
from agentlab.core.traces import Recorder
from agentlab.providers.mock import MockProvider
from agentlab.providers.openai import OpenAIProvider
from agentlab.providers.session import ModelSession, ProviderError
from agentlab.storage.local import Store


@pytest.mark.parametrize(
    ("reference", "answer"), [(True, "1"), ({"ok": True}, '{"ok":1}'), ([False], "[0]")]
)
def test_json_grader_distinguishes_booleans_from_numbers(reference, answer):
    task = Task(id="json", prompt="q", grader="json", ground_truth=reference)
    assert objective_grade(task, answer).passed is False


def test_deep_json_answer_cannot_abort_later_tasks(tmp_path):
    class DeepAnswer(MockProvider):
        def complete(self, request):
            if request.purpose == "answer":
                return Completion(
                    message=Message(role="assistant", content="[" * 1000 + "]" * 1000),
                    provider="mock",
                    model="deep-answer",
                )
            return super().complete(request)

    config = tiny_config()
    config.intervention = "none"
    tasks = [
        Task(id="capital", prompt="q", grader="json", ground_truth=[]),
        Task(id="terse", prompt="q"),
    ]
    bundle = run_experiment(config, tasks, Store(tmp_path), provider_factory=lambda _: DeepAnswer())
    assert len(bundle.runs) == 2
    assert bundle.runs[0].objective.passed is False
    assert Store(tmp_path).get_run(bundle.runs[1].id).answer is not None


def test_unexpected_oracle_error_is_preserved_and_later_tasks_continue(tmp_path, monkeypatch):
    def broken(task, answer):
        raise OverflowError("oracle overflow")

    monkeypatch.setattr("agentlab.core.experiments.objective_grade", broken)
    config = tiny_config()
    config.intervention = "none"
    result = run_experiment(
        config, [Task(id="capital", prompt="q"), Task(id="terse", prompt="q")], Store(tmp_path)
    )
    assert len(result.runs) == 2
    assert result.runs[0].objective.status == "error"
    assert result.runs[0].metrics["objective_passed"] is None
    assert result.status == "partial"


def test_malformed_tool_call_preserves_observable_payload_and_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret")

    def handler(request):
        return httpx.Response(
            200,
            json={
                "id": "r1",
                "model": "test",
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "reasoning_content": "PRIVATE",
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {"name": "calculator", "arguments": "{broken"},
                                }
                            ],
                        },
                    }
                ],
            },
        )

    config = ModelConfig(provider="openai", model="test", api_key_env="TEST_KEY")
    recorder = Recorder("r", tmp_path / "trace.jsonl")
    session = ModelSession(
        OpenAIProvider(config, transport=httpx.MockTransport(handler)), config, recorder, 1
    )
    with pytest.raises(ProviderError):
        session.call([Message(role="user", content="calculate")], purpose="answer")
    trace = recorder.path.read_text()
    assert "{broken" in trace
    assert "PRIVATE" not in trace
    run = Run(
        id="r",
        experiment_id="e",
        task=Task(id="t", prompt="q"),
        seed=1,
        repetition=0,
        stage="baseline",
        trace=recorder.events,
    )
    assert run_metrics(run, 3)["tokens"] == 120
