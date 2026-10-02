# RAEL / Agent Lab

**A local research instrument for agent behavior, predicted evaluation, and judge disagreement.**

RAEL runs an agent through a task, records its observable actions, asks it to predict
its evaluation, and compares that prediction with independent judges and an
objective reference check. An optional intervention produces a linked revision.
Every experiment becomes an inspectable bundle and a portable browser report.

The organizing question: **Can an agent estimate, expose, and improve the reliability
of its own behavior before an external evaluator catches its failures?**

This is an early, competition-neutral MVP. The bundled tasks demonstrate the
measurement pipeline; they are not a benchmark or evidence of general capability.

## Why separate success from judgment?

An answer can be correct and still disappoint a judge. A fluent explanation can
be wrong and still earn a high score. A revision can improve presentation while
reducing accuracy. Collapsing these observations into one number hides the behavior
we want to study.

RAEL stores three separate prediction targets:

- **Panel pass probability:** the probability a strict majority of scoring judges passes the answer.
- **Predicted mean score:** the expected mean of the panel's scalar scores.
- **Objective confidence:** the probability the answer is objectively correct.

Predictions are saved before evaluation begins. Objective checks stay separate
from judge votes. Individual verdicts, disagreement, missing results and failures
remain available in both the data and the interface.

## Run locally

Python 3.11 or later. No Node, database service or frontend build is required.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
agentlab run experiments/predict-your-judge.yaml
```

If your Python installation lacks `ensurepip`, the equivalent uv setup is:

```sh
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -e '.[dev]'
source .venv/bin/activate
agentlab run experiments/predict-your-judge.yaml
```

The default experiment is **offline and explicitly scripted**. It runs 12 tasks,
three judge configurations, and one revision per task through the real harness.
It includes confident errors, rubric conflicts, tool verification and a deliberate
revision regression. Mock judgments and predictions are fixtures, not model inference.

The command prints an experiment ID, individual run IDs and the absolute report
path. Open `results/<experiment-id>/report.html` in a browser, or serve it locally:

```sh
agentlab serve <experiment-id>            # http://127.0.0.1:8765/report.html
agentlab inspect <run-id>
agentlab inspect <run-id> --json
agentlab compare <baseline-id> <revision-id>
agentlab report <experiment-id>
```

All commands accept `--results PATH` to choose the artifact root. `run --verbose`
emits structured JSON log records on stderr. Exit codes: `0` completed, `1` partial
experiment, `2` configuration/lookup error, `130` interrupted.

## Use a real model

Export a key in your shell; `.env.example` documents the variables. RAEL does not
automatically load `.env` files.

```sh
export OPENAI_API_KEY='your-key'
agentlab run experiments/predict-your-judge-openai.yaml
```

The included configuration uses `gpt-4.1-mini`; change `agent.model` to an available
Chat Completions model for your account. The HTTP adapter supports observable
function calls, JSON-mode predictions/judgments, timeouts, explicit retries,
returned model versions and token usage. API behavior follows the official
[Chat Completions documentation](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).
Model/endpoint compatibility varies; unsupported parameters remain visible errors.

For a compatible endpoint, set `AGENTLAB_BASE_URL` (for example,
`http://localhost:1234/v1`) and the key expected by that endpoint. A local server
that ignores authentication can use a non-secret placeholder key. Credentials are
read at the HTTP boundary; request headers and private reasoning fields are not
stored. No live remote model call was used to verify this first implementation;
HTTP request/response conversion is covered by transport tests.

An evaluator inherits the agent model unless its YAML entry supplies its own
`model` object. Separate calls to one model are independent conversations, **not
statistically independent model families**. Price estimates are optional: set
`input_usd_per_million` and `output_usd_per_million` per model configuration. Without
both rates, cost is unknown. Estimates do not include cached-token discounts and
are not billing records.

## Explore the experiment

The same result bundle drives three coordinated views:

1. **Evaluation matrix:** every task, objective check and judge, with paired before/after cells.
2. **Confidence gap:** predicted versus observed mean judge score, with objective outcomes alongside.
3. **Attempt comparison and trace:** answers, probabilities, individual verdicts,
   interventions, exact observable requests and expandable tool events.

Filter by task/tag, confidence errors, judge disagreement, regression, or tool use.
The report is self-contained and can open another `result.json` locally. It makes
no external requests and escapes candidate text before displaying it. Reports
contain task data, answers and prompts: treat them as research artifacts when sharing.

## What an experiment contains

```text
results/
  index.sqlite3                 # ID-to-artifact lookup index
  exp-.../
    config.json                 # resolved model/panel/intervention configuration
    tasks.json                  # exact tasks, including private grading references
    manifest.json               # hashes, source/dependency/runtime provenance
    traces/run-....jsonl         # append-only, fsynced observable events
    runs/run-....json            # each attempt and its metrics
    result.json                 # portable complete experiment bundle
    report.html                 # explorer with this exact bundle embedded
```

Completed attempts checkpoint to disk. Errors and retries remain in the trace.
An interrupted execution keeps its partial records and remains marked `running`;
automatic resume is not implemented. Remote inputs are reproducible as recorded
requests, but seeds do not guarantee identical model outputs.

Metrics include objective success, judge pass rate, complete-panel pass rate,
binary judge disagreement, score spread, Brier errors, score MAE, false confidence
and pessimism, intervention improvement/regression, paired deltas, tool errors,
request latency, known tokens and estimated cost. Coverage and denominators are
explicit. Missing judges are not treated as zero scores; incomplete panels do not
produce a panel calibration score.

## Extend it

| Add | Start here |
| --- | --- |
| A task | Add a validated object to a JSON array; point YAML `tasks` at it |
| A model provider | Implement `Provider.complete(CompletionRequest) -> Completion` and register it in `providers` |
| A different agent | Implement `Agent.attempt` and `Agent.predict`; connect it at the orchestrator's agent construction point |
| A judge | Implement `Evaluator.evaluate`; add config/factory handling while preserving independent inputs |
| A tool | Implement `Tool.spec` and `Tool.invoke`; register it and explicitly allow it on tasks |
| A deterministic grader | Extend `objective_grade`; preserve typed error results and keep references out of public tasks |
| A competition | Translate its records with a `TaskAdapter`; keep rules and formats in `adapters/` |
| An MCP environment | Implement the transport contract in `adapters/mcp.py` and integrate its tools |
| A metric | Add a pure function over stored runs; document its target, missingness and denominator |

Built-in evaluators include rubric judges, binary and scalar criteria, a standalone
pairwise comparison primitive, and a pending human-annotation placeholder. Pairwise
judgment is a Python API, not part of the single-answer panel. The `compare` CLI
compares stored metrics; it does not spend API calls on a new pairwise judgment.
Built-in tools are a bounded arithmetic calculator and search over supplied references.

Read [architecture](docs/architecture.md), [artifact format](docs/experiment-format.md),
[evaluator design](docs/evaluator-design.md), and [competition/MCP adapters](docs/competition-adapters.md).
The explorer assets live inside the Python package so installed wheels can generate reports.

## Verification

```sh
pytest
ruff check src tests
ruff format --check src tests
python -m build
```

Tests cover stage order and leakage boundaries, tool execution, known calibration
values, missing judges, provider retries, malformed outputs, preserved failures,
SQLite/JSON reload, CLI flows and report escaping. See [verification notes](docs/verification.md)
for browser checks and the first implementation's limits.

## Research limits and next steps

The tiny task set and conflicting exposition rubric are intentional probes. The
mock provider supports bundled task IDs only; arbitrary new tasks need a real
provider or another fixture. Reference graders are deliberately narrow: exact,
numeric, JSON equality and substring checks do not establish broad task success.
The `tool_verified` criterion observes successful execution, not whether an answer
faithfully uses the result.

Before making empirical claims, add more tasks, randomized untreated controls,
model-family diversity, confidence intervals, blinded pairwise presentation and
human validation. Prompt separation prevents accidental harness leakage; it is
not proof that a model judge resists prompt injection in candidate text.

Planned: full MCP transport, configurable external agent/tool factories, coding
sandboxes, multimodal payloads, persisted human annotations, resumable runs,
streaming traces, failure clustering and publication figures. No distributed
infrastructure is required for the current slice.

MIT licensed. Not affiliated with a particular model provider or competition.
