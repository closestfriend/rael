import json

import pytest
from test_pipeline import tiny_config

from agentlab.core.evaluators import PairwiseJudge
from agentlab.core.experiments import run_experiment
from agentlab.core.models import Completion, Message, Task
from agentlab.core.traces import Recorder
from agentlab.providers.mock import MockProvider
from agentlab.providers.session import ModelSession, ProviderError
from agentlab.storage.local import Store


class FailingProvider(MockProvider):
    def __init__(self, purpose):
        self.purpose = purpose

    def complete(self, request):
        if request.purpose == self.purpose:
            raise ProviderError("Deliberate outage")
        return super().complete(request)


def test_answer_failure_persists_and_does_not_create_revision(tmp_path):
    result = run_experiment(
        tiny_config(),
        [Task(id="capital", prompt="q")],
        Store(tmp_path),
        provider_factory=lambda _: FailingProvider("answer"),
    )
    assert result.status == "partial"
    assert len(result.runs) == 1
    run = result.runs[0]
    assert run.status == "failed"
    assert run.metrics["cost_usd"] is None
    assert "Deliberate outage" in json.dumps(Store(tmp_path).get_run(run.id).model_dump())


def test_prediction_failure_is_not_retried_after_evaluation(tmp_path):
    config = tiny_config()
    config.intervention = "none"
    result = run_experiment(
        config,
        [Task(id="capital", prompt="q", grader="exact", ground_truth="Canberra")],
        Store(tmp_path),
        provider_factory=lambda _: FailingProvider("prediction"),
    )
    run = result.runs[0]
    assert run.status == "partial"
    assert run.objective.passed is False
    assert run.prediction is None
    assert run.metrics["panel_brier"] is None
    boundary = next(e.seq for e in run.trace if e.type == "evaluation_start")
    assert not any(e.phase == "prediction" and e.seq > boundary for e in run.trace)


def test_judge_outage_remains_missing_not_negative_vote(tmp_path):
    config = tiny_config()
    config.intervention = "none"
    result = run_experiment(
        config,
        [Task(id="capital", prompt="q")],
        Store(tmp_path),
        provider_factory=lambda _: FailingProvider("judge"),
    )
    assert result.runs[0].metrics["panel_passed"] is None
    assert result.runs[0].verdicts[1].status == "error"
    assert result.runs[0].verdicts[1].score is None


def test_self_critique_does_not_receive_external_verdicts(tmp_path):
    config = tiny_config()
    config.intervention = "self_critique"
    result = run_experiment(
        config, [Task(id="capital", prompt="q", ground_truth="PRIVATE")], Store(tmp_path)
    )
    revision = result.runs[1]
    call = next(e for e in revision.trace if e.type == "model_call" and e.phase == "critique")
    data = json.dumps(call.data)
    assert "PRIVATE" not in data
    assert "evaluator_id" not in data
    assert revision.intervention.kind == "self_critique"


def test_pairwise_contract_and_pending_human(tmp_path):
    config = tiny_config()
    session = ModelSession(
        MockProvider(), config.agent, Recorder("pair", tmp_path / "pair.jsonl"), 1
    )
    result = PairwiseJudge(session, "Accuracy").compare(
        Task(id="capital", prompt="q").public(), "A", "B"
    )
    assert result.winner == "tie"
    assert any(e.phase == "pairwise" for e in session.recorder.events)
    config.intervention = "none"
    from agentlab.core.models import EvaluatorConfig

    config.evaluators.append(EvaluatorConfig(id="annotator", kind="human"))
    bundle = run_experiment(config, [Task(id="capital", prompt="q")], Store(tmp_path / "store"))
    run = bundle.runs[0]
    assert run.verdicts[-1].status == "pending"
    assert run.metrics["judges_expected"] == 3
    assert run.metrics["judge_coverage"] == 1


def test_invalid_tools_fail_before_experiment_directory(tmp_path):
    with pytest.raises(ValueError, match="Unknown tools"):
        run_experiment(
            tiny_config(), [Task(id="a", prompt="q", available_tools=["shell"])], Store(tmp_path)
        )
    assert not list(tmp_path.glob("exp-*"))


def test_malformed_prediction_retains_raw_observable_response(tmp_path):
    class Malformed(MockProvider):
        def complete(self, request):
            if request.purpose == "prediction":
                return Completion(
                    message=Message(role="assistant", content='{"pass_probability": 4}'),
                    provider="mock",
                    model="malformed",
                )
            return super().complete(request)

    config = tiny_config()
    config.intervention = "none"
    result = run_experiment(
        config,
        [Task(id="capital", prompt="q")],
        Store(tmp_path),
        provider_factory=lambda _: Malformed(),
    )
    run = result.runs[0]
    assert run.status == "partial"
    assert any(e.type == "model_result" and e.phase == "prediction" for e in run.trace)
    assert run.prediction is None
