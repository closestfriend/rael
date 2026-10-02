"""A portable report embeds the same validated bundle used by the CLI."""

from importlib.resources import files
from pathlib import Path

from agentlab.core.models import Experiment


def render_report(experiment: Experiment) -> str:
    assets = files("agentlab").joinpath("apps/explorer")
    data = (
        experiment.model_dump_json()
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )
    return (
        assets.joinpath("index.html")
        .read_text(encoding="utf-8")
        .replace("/* EXPLORER_STYLE */", assets.joinpath("style.css").read_text(encoding="utf-8"))
        .replace("/* EXPLORER_SCRIPT */", assets.joinpath("app.js").read_text(encoding="utf-8"))
        .replace("EXPERIMENT_DATA", data)
    )


def write_report(experiment: Experiment, directory: Path) -> Path:
    path = directory / "report.html"
    path.write_text(render_report(experiment), encoding="utf-8")
    return path
