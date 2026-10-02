import json
import subprocess
import sys
from pathlib import Path

from test_pipeline import tiny_config

from agentlab.core.experiments import run_experiment
from agentlab.core.models import Task
from agentlab.reporting import render_report
from agentlab.storage.local import Store

ROOT = Path(__file__).resolve().parents[1]


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "agentlab", *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_cli_run_inspect_compare_report(tmp_path):
    execution = cli("run", "experiments/predict-your-judge.yaml", "--results", tmp_path)
    assert execution.returncode == 0, execution.stderr
    artifact = next(tmp_path.glob("exp-*/result.json"))
    bundle = json.loads(artifact.read_text())
    assert len(bundle["runs"]) == 24
    a, b = bundle["runs"][:2]
    inspected = cli("inspect", a["id"], "--results", tmp_path, "--json")
    assert json.loads(inspected.stdout)["answer"] == "Sydney"
    compared = cli("compare", a["id"], b["id"], "--results", tmp_path)
    assert json.loads(compared.stdout)["objective_improved"] is True
    report = cli("report", bundle["id"], "--results", tmp_path)
    assert report.returncode == 0, report.stderr
    assert (artifact.parent / "report.html").is_file()


def test_invalid_configuration_has_useful_exit_and_no_bundle(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: test\ntasks: missing.json\nevaluators: []\n")
    result = cli("run", bad, "--results", tmp_path / "results")
    assert result.returncode == 2
    assert "error:" in result.stderr.lower()
    assert not list((tmp_path / "results").glob("exp-*"))


def test_html_embedded_data_cannot_terminate_script(tmp_path):
    bundle = run_experiment(tiny_config(), [Task(id="capital", prompt="q")], Store(tmp_path))
    bundle.runs[0].answer = '</script><img src=x onerror="alert(1)">'
    html = render_report(bundle)
    assert "</script><img src=x" not in html
    assert "\\u003c/script\\u003e" in html
