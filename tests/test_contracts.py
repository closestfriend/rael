import pytest
from pydantic import ValidationError

from agentlab.core.models import ExperimentConfig, Prediction, Task
from agentlab.core.tools import Calculator


def test_public_task_excludes_ground_truth_and_private_metadata():
    task = Task(id="a", prompt="Question", ground_truth="SECRET", metadata={"private": 42})
    assert "SECRET" not in task.public().model_dump_json()
    assert "metadata" not in task.public().model_dump()
    assert "ground_truth" not in task.public().model_dump()


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf")])
def test_predictions_reject_invalid_probabilities(value):
    with pytest.raises(ValidationError):
        Prediction(pass_probability=value, predicted_score=0.5, confidence=0.5)


def test_unknown_config_fields_are_rejected():
    with pytest.raises(ValidationError):
        ExperimentConfig(name="x", tasks="x.json", unexpected=True)


def test_duplicate_evaluator_ids_are_rejected():
    with pytest.raises(ValidationError, match="unique"):
        ExperimentConfig(
            name="x",
            tasks="x.json",
            evaluators=[
                {"id": "same", "kind": "binary", "criterion": "nonempty"},
                {"id": "same", "kind": "binary", "criterion": "nonempty"},
            ],
        )


def test_calculator_evaluates_arithmetic_without_python_execution():
    assert Calculator().invoke({"expression": "(17 * 23) - 6"}) == {"value": 385}
    for expression in ["__import__('os')", "2 ** 99999999", "[1] * 9", "1 / 0"]:
        with pytest.raises(ValueError):
            Calculator().invoke({"expression": expression})
