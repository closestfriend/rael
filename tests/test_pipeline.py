import json

from agentlab.core.experiments import run_experiment
from agentlab.core.models import ExperimentConfig, Task
from agentlab.storage.local import Store


def tiny_config():
    return ExperimentConfig(
        name="test",
        tasks="unused.json",
        intervention="feedback",
        evaluators=[
            {"id": "format", "kind": "binary", "criterion": "single_token"},
            {"id": "content", "kind": "rubric", "rubric": "Check factual correctness."},
            {"id": "detail", "kind": "scalar", "criterion": "explanation"},
        ],
    )


def test_pipeline_seals_predictions_links_revision_and_reloads_artifacts(tmp_path):
    task = Task(
        id="capital",
        prompt="What is the capital of Australia? One word.",
        ground_truth="Canberra",
        grader="exact",
        tags=["factual"],
    )
    store = Store(tmp_path)
    bundle = run_experiment(tiny_config(), [task], store)
    assert bundle.status == "completed"
    before, after = bundle.runs
    assert before.objective.passed is False
    assert after.objective.passed is True
    assert after.parent_id == before.id
    assert before.prediction.pass_probability == 0.9
    types = [e.type for e in before.trace]
    assert types.index("prediction") < types.index("evaluation_start")
    model_calls = [e for e in before.trace if e.type == "model_call"]
    assert "Canberra" not in json.dumps(model_calls[0].data)
    assert "ground_truth" not in json.dumps(model_calls[0].data)
    assert store.get_run(before.id).id == before.id
    assert store.get_experiment(bundle.id).metrics["pairs"]["objective_improvement_rate"] == 1.0
    path = tmp_path / bundle.id
    assert json.loads((path / "result.json").read_text())["status"] == "completed"
    events = [
        json.loads(line)
        for line in (path / "traces" / f"{before.id}.jsonl").read_text().splitlines()
    ]
    assert [e["seq"] for e in events] == list(range(len(events)))


def test_tool_use_is_observable_and_ground_truth_is_not_needed(tmp_path):
    task = Task(
        id="multiply",
        prompt="Use calculator to compute 17 * 23. Only the number.",
        context={"expression": "17 * 23"},
        available_tools=["calculator"],
        grader="numeric",
        ground_truth=391,
        tags=["arithmetic"],
    )
    bundle = run_experiment(tiny_config(), [task], Store(tmp_path))
    run = bundle.runs[0]
    assert run.objective.passed is True
    assert any(e.type == "tool_call" for e in run.trace)
    assert any(e.type == "tool_result" and e.data["ok"] for e in run.trace)
