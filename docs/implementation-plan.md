# First vertical slice implementation plan

**Goal:** Run, persist, inspect and compare an agent's predictions and independently
graded baseline/revision attempts, then explore the real output in a browser.

**Spec:** [architecture.md](architecture.md). Execution is native in this session,
as requested: architecture first, then implement autonomously and verify.

## Constraints and review focus

Python >=3.11; Pydantic, PyYAML and HTTPX only at runtime. Public task views must
exclude answer keys. Failed/pending judges cannot masquerade as failures or
successes. Predictions precede all evaluation. Retried calls retain their errors.
Portable reports must escape untrusted answers and work without a network.

## Work sequence

- [x] Create package/config skeleton and failing contract tests in `tests/`.
  Validate probability bounds, unknown fields, duplicate task/evaluator IDs,
  tool allowlists and invalid experiment paths before creating a bundle.
- [x] Implement `core/models.py`, `core/protocols.py`, `core/tools.py`,
  `core/traces.py`, `providers/mock.py`, `providers/openai.py` and config loading.
  Use an injected HTTP transport to exercise actual request/response conversion,
  tool round trips, missing usage, malformed responses, retries, and redaction.
- [x] Implement `core/agents.py`, `core/evaluators.py`, `core/interventions.py`.
  Tests assert that public prompts contain no ground truth or prior judge output;
  objective grading, rubric grading, pairwise choice and pending human verdicts
  remain separate. Calculator tests reject names, calls and resource-heavy input.
- [x] Implement `core/experiments.py`, `core/metrics.py`, `storage/local.py`.
  Run one task end-to-end; verify prediction event ordering, persisted failures,
  revision linkage, literal expected Brier/MAE/delta values and artifact reload.
- [x] Add 12 task fixtures, mock/live experiment YAML, CLI run/inspect/compare/
  report/serve workflows, extension examples and report packaging. Run the whole
  test suite and bundled experiment; inspect JSON, JSONL and SQLite consistency.
- [x] Build the matrix, confidence-gap plot and before/after trace explorer from
  `result.json`. Use generated data to verify selection, filtering, attempt
  switching, event expansion, mobile layout and error handling in a browser.
- [x] Write README and format/evaluator/adapter docs covering only shipped
  behavior, run install/package/CLI tests, and record remaining limitations.

## Acceptance commands

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/agentlab run experiments/predict-your-judge.yaml
.venv/bin/agentlab inspect <run-id>
.venv/bin/agentlab compare <baseline-id> <revision-id>
.venv/bin/agentlab report <experiment-id>
.venv/bin/agentlab serve <experiment-id>
```

Live API verification is contingent on an explicitly configured environment key;
mock success alone must never be described as a successful remote model call.

Browser limitation: desktop flow verified; dedicated mobile check blocked by browser URL policy. Live API requires a configured key and was not run.
