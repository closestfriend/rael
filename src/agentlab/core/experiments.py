"""Sequential orchestration with explicit evaluation boundaries and checkpoints."""

import hashlib
import importlib.metadata
import json
import logging
import platform
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from agentlab import __version__
from agentlab.core.agents import ToolAgent
from agentlab.core.evaluators import (
    CriterionEvaluator,
    HumanEvaluator,
    RubricEvaluator,
    objective_grade,
)
from agentlab.core.interventions import FeedbackIntervention, SelfCritiqueIntervention
from agentlab.core.metrics import experiment_metrics, run_metrics
from agentlab.core.models import Experiment, ExperimentConfig, ModelConfig, Run, Task, Verdict, now
from agentlab.core.protocols import Provider
from agentlab.core.tools import tool_registry
from agentlab.core.traces import Recorder
from agentlab.providers import make_provider
from agentlab.providers.session import ModelSession
from agentlab.storage.local import Store

logger = logging.getLogger("agentlab")


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def provenance(config, tasks):
    package = Path(__file__).resolve().parents[1]
    sources = {
        str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(package.rglob("*"))
        if path.suffix in {".py", ".html", ".css", ".js"}
    }
    return {
        "package_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": {
            name: importlib.metadata.version(name) for name in ("pydantic", "PyYAML", "httpx")
        },
        "config_sha256": digest(config.model_dump()),
        "tasks_sha256": digest([t.model_dump() for t in tasks]),
        "source_sha256": digest(sources),
        "source_files": sources,
        "synthetic_agent": config.agent.provider == "mock",
        "reproduction": "Recorded inputs and versions; remote determinism is not guaranteed",
    }


def run_experiment(
    config: ExperimentConfig,
    tasks: list[Task],
    store: Store,
    *,
    provider_factory: Callable[[ModelConfig], Provider] = make_provider,
    progress: Callable[[Run], None] | None = None,
) -> Experiment:
    if not tasks or len({t.id for t in tasks}) != len(tasks):
        raise ValueError("Tasks must be nonempty with unique IDs")
    for task in tasks:
        unknown = set(task.available_tools) - set(tool_registry(task.references))
        if unknown:
            raise ValueError(f"Unknown tools on {task.id}: {sorted(unknown)}")
    experiment = Experiment(
        id=f"exp-{uuid4().hex[:16]}",
        name=config.name,
        config=config,
        tasks=tasks,
        manifest=provenance(config, tasks),
    )
    store.start(experiment)
    expected_judges = sum(e.kind != "human" for e in config.evaluators)
    criteria = [e.model_dump(exclude={"model"}) for e in config.evaluators if e.kind != "human"]

    def attempt(task, seed, repetition, baseline=None):
        run = Run(
            id=f"run-{uuid4().hex[:16]}",
            experiment_id=experiment.id,
            task=task,
            seed=seed,
            repetition=repetition,
            stage="revision" if baseline else "baseline",
            parent_id=baseline.id if baseline else None,
        )
        experiment.runs.append(run)
        store.save_run(run)
        store.save(experiment)
        recorder = Recorder(run.id, store.directory(experiment.id) / "traces" / f"{run.id}.jsonl")
        recorder.emit(
            "task_received",
            "setup",
            task=task.public().model_dump(),
            seed=seed,
            repetition=repetition,
            stage=run.stage,
            parent_id=run.parent_id,
        )
        session = ModelSession(provider_factory(config.agent), config.agent, recorder, seed)
        agent = ToolAgent(session, config.max_tool_rounds, criteria)
        try:
            if baseline:
                strategy = (
                    FeedbackIntervention()
                    if config.intervention == "feedback"
                    else SelfCritiqueIntervention(session)
                )
                run.intervention = strategy.create(baseline)
                recorder.emit("intervention", "intervention", **run.intervention.model_dump())
            run.answer, messages = agent.attempt(
                task.public(), run.intervention, baseline.answer if baseline else None
            )
            recorder.emit("final_answer", "answer", answer=run.answer)
            run.prediction = agent.predict(messages, criteria)
        except Exception as exc:
            run.errors.append(f"{type(exc).__name__}: {exc}")
            recorder.emit("stage_error", "agent", error=run.errors[-1])
        if run.answer is not None:
            # Even failed prediction is visible; external scoring still measures the attempted answer.
            # No later prediction call is permitted after crossing this boundary.
            recorder.emit(
                "evaluation_start", "evaluation", prediction_available=run.prediction is not None
            )
            try:
                run.objective = objective_grade(task, run.answer)
            except Exception as exc:
                run.objective = Verdict(
                    evaluator_id="objective",
                    version="1",
                    kind=task.grader or "none",
                    status="error",
                    error=f"Objective grader failed ({type(exc).__name__})",
                )
                run.errors.append(run.objective.error)
            if run.objective:
                recorder.emit("objective_result", "evaluation", **run.objective.model_dump())
            evidence = [e.data for e in recorder.events if e.type == "tool_result"]
            for evaluator_config in config.evaluators:
                recorder.emit("evaluator_call", "evaluation", config=evaluator_config.model_dump())
                try:
                    if evaluator_config.kind == "rubric":
                        model_config = evaluator_config.model or config.agent
                        judge_session = ModelSession(
                            provider_factory(model_config), model_config, recorder, seed
                        )
                        evaluator = RubricEvaluator(evaluator_config, judge_session)
                    elif evaluator_config.kind == "human":
                        evaluator = HumanEvaluator(evaluator_config)
                    else:
                        evaluator = CriterionEvaluator(evaluator_config)
                    verdict = evaluator.evaluate(task.public(), run.answer, evidence)
                except Exception as exc:
                    verdict = Verdict(
                        evaluator_id=evaluator_config.id,
                        version=evaluator_config.version,
                        kind=evaluator_config.kind,
                        status="error",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    run.errors.append(f"{evaluator_config.id}: {verdict.error}")
                run.verdicts.append(verdict)
                recorder.emit("evaluator_result", "evaluation", **verdict.model_dump())
        run.status = "failed" if run.answer is None else "partial" if run.errors else "completed"
        run.finished_at = now()
        recorder.emit("run_finished", "summary", status=run.status)
        run.trace = recorder.events
        run.metrics = run_metrics(run, expected_judges)
        store.save_run(run)
        experiment.metrics = experiment_metrics(experiment.runs)
        store.save(experiment)
        logger.info(
            json.dumps(
                {
                    "event": "run_finished",
                    "run_id": run.id,
                    "task_id": task.id,
                    "status": run.status,
                }
            )
        )
        if progress:
            progress(run)
        return run

    for seed in config.seeds:
        for repetition in range(config.repetitions):
            for task in tasks:
                baseline = attempt(task, seed, repetition)
                if config.intervention != "none" and baseline.answer is not None:
                    attempt(task, seed, repetition, baseline)
    experiment.status = (
        "completed" if all(r.status == "completed" for r in experiment.runs) else "partial"
    )
    experiment.finished_at = now()
    experiment.metrics = experiment_metrics(experiment.runs)
    store.save(experiment)
    return experiment
