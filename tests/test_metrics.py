import pytest

from agentlab.core.metrics import run_metrics
from agentlab.core.models import Prediction, Run, Task, Verdict


def sample_run():
    return Run(
        id="r",
        experiment_id="e",
        task=Task(id="t", prompt="q"),
        seed=1,
        repetition=0,
        stage="baseline",
        status="completed",
        prediction=Prediction(pass_probability=0.8, predicted_score=0.9, confidence=0.9),
        objective=Verdict(
            evaluator_id="objective", version="1", kind="exact", score=0, passed=False
        ),
        verdicts=[
            Verdict(evaluator_id="a", version="1", kind="rubric", score=1, passed=True),
            Verdict(evaluator_id="b", version="1", kind="rubric", score=0, passed=False),
            Verdict(evaluator_id="c", version="1", kind="rubric", score=1, passed=True),
        ],
    )


def test_hand_calculated_calibration_disagreement_and_objective_separation():
    metrics = run_metrics(sample_run(), expected_judges=3)
    assert metrics["judge_mean_score"] == pytest.approx(2 / 3)
    assert metrics["judge_disagreement"] == pytest.approx(2 / 3)
    assert metrics["panel_passed"] is True
    assert metrics["panel_brier"] == pytest.approx(0.04)
    assert metrics["objective_brier"] == pytest.approx(0.81)
    assert metrics["score_mae"] == pytest.approx(0.9 - 2 / 3)
    assert metrics["objective_false_confidence"] is True


def test_failed_judge_does_not_count_as_zero_or_complete_panel():
    run = sample_run()
    run.verdicts[1] = Verdict(
        evaluator_id="b", version="1", kind="rubric", status="error", error="unavailable"
    )
    metrics = run_metrics(run, expected_judges=3)
    assert metrics["judge_mean_score"] == 1
    assert metrics["judge_coverage"] == pytest.approx(2 / 3)
    assert metrics["panel_passed"] is None
    assert metrics["panel_brier"] is None
    assert metrics["score_mae"] is None


def test_no_calls_has_zero_cost_but_failed_call_has_unknown_cost():
    from agentlab.core.models import TraceEvent

    run = sample_run()
    assert run_metrics(run, 3)["cost_usd"] == 0
    run.trace = [
        TraceEvent(seq=0, run_id="r", phase="answer", type="model_call", data={"call_id": "c1"})
    ]
    metrics = run_metrics(run, 3)
    assert metrics["cost_usd"] is None
    assert metrics["tokens"] is None
