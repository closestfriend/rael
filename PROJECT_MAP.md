# RAEL project map

A one-page orientation for anyone (human or agent) changing this code. Toured at version 0.1.0.

## What it is

`agentlab` is a local research tool that asks whether an AI agent can predict how it will be graded. For each task it makes the agent answer, then write down three probabilities (a strict majority of judges passes it, the judges' mean score, it is objectively correct). Only after those are recorded does it grade the answer two ways: a private answer key (`objective_grade`) and a panel of judges that never see the key. Optionally the judges' notes go back to the agent for a linked revision. Everything is saved per experiment as JSON and JSONL, and one self-contained `report.html` explores it. The default run uses a scripted mock provider (an offline fixture, not model research).

Stack: Python 3.11+, `pydantic` (records), `PyYAML` (experiment files), `httpx` (OpenAI-compatible Chat Completions). No Node, database service or build step.

## Districts

| District | Paths | Job |
| --- | --- | --- |
| Front Desk | `src/agentlab/cli.py`, `config.py`, `adapters/json_tasks.py` | Parse commands (`run inspect compare report serve`), load YAML, load tasks |
| Invigilator | `core/experiments.py` (`run_experiment`, inner `attempt`) | Orchestrates stages; owns the prediction-before-evaluation boundary |
| Telephone Line | `providers/session.py`, `providers/openai.py`, `providers/mock.py` | Every model call: retries, trace events, HTTP or scripted reply |
| Exam Hall | `core/agents.py`, `core/tools.py` | Tool-using agent loop, separate prediction call, calculator and search |
| Marking Room | `core/evaluators.py` | `objective_grade`, rubric/criterion/human evaluators, pairwise primitive |
| Retake Desk | `core/interventions.py` | Feedback or self-critique text for the revision attempt |
| Scorekeeper | `core/metrics.py` | Brier errors, coverage, disagreement, paired deltas |
| Records | `core/traces.py`, `storage/local.py` | Append-only JSONL, atomic JSON, SQLite ID index |
| Gallery | `reporting.py`, `apps/explorer/` | Embeds the bundle into one HTML file |
| Forms | `core/models.py`, `core/protocols.py` | Pydantic schemas and structural contracts |

## One run, in order

`agentlab run experiments/predict-your-judge.yaml`

1. `cli.main` → `config.load_config` → `(ExperimentConfig, list[Task])`.
2. `run_experiment` preflights tasks and tools, builds `Experiment`, `provenance()` manifest, `Store.start` writes `config.json`, `tasks.json`, `manifest.json`, `result.json` and the SQLite row.
3. For each seed, repetition and task: `attempt()` creates a baseline `Run` and a `Recorder` on `traces/<run-id>.jsonl`, emits `task_received` with `task.public()`.
4. `ToolAgent.attempt` loops over `ModelSession.call(purpose="answer")`, running allowed tools, until a reply has no tool calls.
5. `ToolAgent.predict` makes a separate JSON call and validates a `Prediction`.
6. `evaluation_start` event, then `objective_grade(task, answer)` against the private `ground_truth`.
7. Each evaluator: rubric judges get a fresh `ModelSession` and see only the public task, answer, tool evidence and their own rubric. A failing judge becomes `Verdict(status="error")`.
8. Status set (`completed`, `partial`, `failed`), `run_metrics`, checkpoint (`save_run`, `experiment_metrics`, `save`).
9. If `intervention` is not `none` and the baseline has an answer: a second `attempt` with the baseline, `FeedbackIntervention` or `SelfCritiqueIntervention`.
10. Final experiment status and metrics, `write_report`, `summary`, exit code (0 completed, 1 partial, 2 error, 130 interrupted).

## Parts, in → out

| Piece | In → out |
| --- | --- |
| `cli.main` | argv → exit code |
| `load_config` | YAML path → `(ExperimentConfig, list[Task])` |
| `Task.public()` | `Task` → `PublicTask` (what a model may see) |
| `run_experiment` / `attempt` | config, tasks, store → `Experiment` of baseline and revision `Run`s |
| `ModelSession.call` | messages + purpose → `Completion`; emits `model_call`, `model_result`, `error`, `retry` |
| `ToolAgent.attempt` / `predict` | public task → `(answer, messages)`; transcript → `Prediction` |
| `tool_registry` | references → `calculator`, `search` |
| `make_provider` | `ModelConfig` → `MockProvider` or `OpenAIProvider` |
| `objective_grade` | `Task` + answer → `Verdict` or `None` |
| `RubricEvaluator` / `CriterionEvaluator` / `HumanEvaluator` | public task, answer, evidence → `Verdict` |
| `FeedbackIntervention` / `SelfCritiqueIntervention` | baseline `Run` → `InterventionRecord` |
| `Recorder.emit` | event → one fsynced JSON line |
| `run_metrics` / `compare_runs` / `experiment_metrics` | run(s) → metrics; missing is never zero |
| `Store`, `render_report` | atomic JSON plus SQLite index; bundle embedded in `index.html` |

## Where state lives

- Secrets: environment variables only (`OPENAI_API_KEY` by default via `api_key_env`, optional `AGENTLAB_BASE_URL`). Never stored in artifacts; `.env` is not auto-loaded.
- Per experiment under `results/exp-<16 hex>/`: `config.json`, `tasks.json` (includes the answer key), `manifest.json`, `runs/`, `traces/`, `result.json`, `report.html`. Lookup index at `results/index.sqlite3`.

## Change map

| To do this | Go to |
| --- | --- |
| Add a deterministic grader | branch in `objective_grade` (`core/evaluators.py`) and the `Task.grader` Literal in `core/models.py` |
| Add a task | object in a JSON array (`tasks/*.json`); the mock supports only bundled task IDs |
| Add a model provider | `providers/__init__.make_provider` and the `ModelConfig.provider` Literal |
| Plug in a different agent | replace the `ToolAgent(...)` construction in `attempt()` (no factory yet) |
| Add a judge kind | `EvaluatorConfig.kind`, the branch in `attempt()`, a new `Evaluator` |
| Add a tool | `core/tools.py` plus `tool_registry`; allow it per task in `available_tools` |
| Add a metric | `run_metrics` / `experiment_metrics` in `core/metrics.py` |
| Change what a model can see | `PublicTask` fields in `core/models.py` |
| Change report contents | `render_report` and `apps/explorer/app.js` |
| Resume interrupted runs | the loop at the end of `run_experiment`, plus `Store` |

## Known sharp edges (from the tour)

- `report.html` and `result.json` embed each task's `ground_truth` and private metadata.
- `PublicTask.tags` and the judges' rubric text are sent to the agent and judges.
- `apps/explorer/app.js` interpolates `seed`, `repetition` and `resources.tokens` without `esc()`.
- `agentlab serve` does not check the Host header and lists the results directory.
- `repetitions` reuse one seed; `repetition` is not mixed into the request seed.
- After Ctrl-C, `runs/<id>.json` has empty `trace` and `answer`; the events are in the JSONL.
