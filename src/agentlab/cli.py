"""Run and inspect experiments without editing Python source."""

import argparse
import functools
import json
import logging
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agentlab.config import load_config
from agentlab.core.experiments import run_experiment
from agentlab.core.metrics import compare_runs
from agentlab.reporting import write_report
from agentlab.storage.local import Store


def number(value, digits=3):
    return "unknown" if value is None else f"{value:.{digits}f}"


def summary(experiment):
    label = (
        "SCRIPTED FIXTURE — not model research results"
        if experiment.manifest.get("synthetic_agent")
        else "Live model experiment"
    )
    print(f"{experiment.name}  [{experiment.status}]\n{label}\nExperiment: {experiment.id}")
    for stage, metrics in experiment.metrics["stages"].items():
        print(
            f"  {stage:8s}  objective={number(metrics['objective_success_rate'])} "
            f"({metrics['objectively_graded']}/{metrics['objective_eligible']} graded)  "
            f"judge score={number(metrics['judge_mean_score'])}  "
            f"panel Brier={number(metrics['panel_brier'])}"
        )
    pairs = experiment.metrics["pairs"]
    print(
        f"  {pairs['count']} pairs  improvement={number(pairs['objective_improvement_rate'])}  "
        f"regression={number(pairs['objective_regression_rate'])}  score delta={number(pairs['mean_score_delta'])}"
    )
    resources = experiment.metrics["resources"]
    print(
        f"  cost USD={number(resources['cost_usd'], 6)}  tokens={resources['tokens']}  "
        f"request/tool latency ms={number(resources['latency_ms'], 1)}"
    )


def parser():
    root = argparse.ArgumentParser(
        prog="agentlab", description="RAEL: inspectable agent evaluation"
    )
    commands = root.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("run", "Run an experiment YAML"),
        ("inspect", "Inspect a stored run"),
        ("compare", "Compare two runs"),
        ("report", "Generate a portable report"),
        ("serve", "Serve one experiment on localhost"),
    ]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument(
            "--results",
            type=Path,
            default=Path("results"),
            help="Artifact root (default: ./results)",
        )
        if name == "run":
            command.add_argument("config", type=Path)
            command.add_argument(
                "--verbose", action="store_true", help="JSON log records on stderr"
            )
        elif name == "compare":
            command.add_argument("before")
            command.add_argument("after")
        else:
            command.add_argument("id")
        if name == "inspect":
            command.add_argument(
                "--json", action="store_true", help="Full run with trace and metrics"
            )
        if name == "serve":
            command.add_argument("--port", type=int, default=8765)
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "run":
            config, tasks = load_config(args.config)
            if args.verbose:
                logging.basicConfig(level=logging.INFO, format="%(message)s")
            store = Store(args.results)

            def progress(run):
                print(f"{run.task.id:16s} {run.stage:8s} {run.status:9s} {run.id}", file=sys.stderr)

            experiment = run_experiment(config, tasks, store, progress=progress)
            path = write_report(experiment, store.directory(experiment.id))
            summary(experiment)
            print(f"Report: {path}\nData: {path.parent / 'result.json'}")
            return 0 if experiment.status == "completed" else 1
        store = Store(args.results)
        if args.command == "inspect":
            run = store.get_run(args.id)
            if args.json:
                print(run.model_dump_json(indent=2))
            else:
                print(
                    f"{run.id}  {run.task.id} / {run.stage}  [{run.status}]\nAnswer: {run.answer}"
                )
                print(
                    json.dumps(
                        {
                            "prediction": run.prediction.model_dump() if run.prediction else None,
                            "metrics": run.metrics,
                            "errors": run.errors,
                        },
                        indent=2,
                    )
                )
        elif args.command == "compare":
            print(
                json.dumps(
                    compare_runs(store.get_run(args.before), store.get_run(args.after)), indent=2
                )
            )
        else:
            experiment = store.get_experiment(args.id)
            directory = store.directory(experiment.id)
            report = write_report(experiment, directory)
            if args.command == "report":
                summary(experiment)
                print(f"Report: {report}")
            else:
                handler = functools.partial(SimpleHTTPRequestHandler, directory=str(directory))
                with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
                    print(f"http://127.0.0.1:{server.server_port}/report.html", flush=True)
                    server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped. Existing artifacts and traces are preserved.", file=sys.stderr)
        return 130
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"agentlab error: {exc}", file=sys.stderr)
        return 2
    return 0
