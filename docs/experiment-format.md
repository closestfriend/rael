# Experiment format v1.0

`core/models.py` is the validated source of truth. Unknown fields are rejected.
All probabilities and scores are finite numbers in `[0,1]`; costs are USD and
durations are milliseconds. IDs are filesystem-safe identifiers.

An `Experiment` contains configuration, full task snapshots, provenance, runs and
aggregate metrics. A `Run` is one task/seed/repetition/stage attempt. Revisions
reference their baseline through `parent_id`; they never overwrite it.

A public task excludes `ground_truth`, `grader` and private `metadata`. Only the
public task is supplied to agent and model judges. Do not put private answers in
`context`, `references` or `tags`: these fields intentionally go to the models.

## Trace events

Each JSONL line has `schema_version`, zero-based `seq`, `timestamp` (UTC), `run_id`,
`phase`, `type` and `data`. Events include:

- `task_received`, `model_call`, `model_result`, `tool_call`, `tool_result`;
- `final_answer`, `prediction`, `evaluation_start`, `objective_result`;
- `evaluator_call`, `evaluator_result`, `intervention`, `retry`, `error`,
  `stage_error`, `run_finished`.

Requests contain exact public messages, tool schemas, requested model parameters
and seed. Responses retain exposed content, tool calls, usage, returned model,
response ID and fingerprint. Provider-private reasoning and HTTP headers are
excluded. A malformed tool argument is preserved as `raw_tool_calls` in a
`model_result` marked `invalid`, before the error event.

The append-only trace is flushed and fsynced before execution advances. JSON
snapshots use atomic rename. SQLite indexing follows snapshot writes; it is not a
cross-file transaction. After an interrupted write, inspect JSON/JSONL directly.
There is no automatic index rebuild or resume command yet.

## Status and missingness

Run statuses: `running`, `completed`, `partial` (answer exists, a later stage
failed), `failed` (no answer). Experiment status is `completed` only if all recorded
runs completed. A baseline without an answer has no revision. Its absence is not
an intervention success.

Verdicts are `ok`, `error` or `pending`. An error/pending verdict has no score.
Human placeholders are excluded from the scoring-panel denominator. The objective
reference check is a separate verdict, never a judge vote.

Resource totals include agent, prediction, judges and critique. A request whose
usage was lost makes total tokens/cost unknown; `known_tokens`/`known_cost_usd`
retain the known subtotal. Offline fixture usage is explicitly zero. Latency is
summed request/tool time, not end-to-end wall-clock time. Start/finish timestamps
are also retained.

## Reproducibility

The manifest records config/task SHA-256, every packaged source file's SHA-256,
Python/platform/package versions and installed runtime dependency versions. Model
responses record returned versions when exposed. Preserve the source revision and
artifact together; hashes identify code but do not embed it. Prompts are in traces,
and judge rubric versions are in configuration and individual verdicts.

Example read without SQLite:

```python
from pathlib import Path
from agentlab.core.models import Experiment
bundle = Experiment.model_validate_json(Path('results/exp-.../result.json').read_text())
for run in bundle.runs:
    print(run.task.id, run.stage, run.metrics['panel_brier'])
```
