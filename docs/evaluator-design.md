# Evaluator design and measurement

## Independent inputs

The agent sees public judge criteria before attempting the task. After the final
answer, a separate model call emits a validated `Prediction`. Only then does the
harness call the objective grader and each panel member. A failed prediction is
stored as a stage error: the answer can still be graded, but it receives no
calibration score and no prediction is collected after feedback.

Each rubric judge has a fresh conversation containing only the public task,
answer, tool observations, its own rubric/version and output schema. Neither
answer keys, agent confidence, prior judge verdicts nor intervention text are
sent to judges. Candidate text is explicitly designated as data, although this
is not a guarantee against judge prompt injection.

## Implemented evaluators

- **Objective:** exact stripped string equality; numeric equality with absolute
  tolerance `1e-8`; recursive JSON equality distinguishing booleans from numbers;
  or substring containment. A grading exception becomes an error verdict.
- **Rubric:** model-produced score, confidence, rationale, dimensions and evidence.
  Pass is computed by the harness from the configured threshold.
- **Binary/scalar criteria:** nonempty, single whitespace-delimited token,
  successful tool execution, and explanation length (word count / 12, capped at 1).
  These are narrow behavioral checks, not correctness or evidence-fidelity claims.
- **Human:** a pending structured placeholder, without an annotation persistence UI.
- **Pairwise:** `PairwiseJudge.compare(public_task, answer_a, answer_b)` returns
  `a`, `b` or `tie`, confidence and rationale. It requires a `ModelSession` and
  records the call. Not part of the ordinary scoring panel. Order balancing is
  the experimenter's responsibility.

## Targets and denominators

For predictions `p` and observed binary events `y`, Brier error is `(p-y)^2`.
Panel Brier uses `pass_probability` and strict majority pass. Objective Brier uses
`confidence` and the private reference result. Mean absolute score error uses
`predicted_score` and observed mean judge score. These targets are not interchangeable.

Panel pass and score calibration require every configured non-human judge to
return a valid verdict. Available judges still contribute to the displayed mean,
score spread and disagreement, accompanied by coverage. Disagreement is the
fraction of scored judge pairs that disagree on pass/fail; one judge alone has
undefined disagreement. A tied even-sized panel does not pass.

Stage objective success is over answers with successful objective grading.
`objective_success_per_eligible_attempt` also accounts for failed attempts among
tasks with a reference grader. Counts distinguish eligible, graded and failed
attempts. Every average has a corresponding sample count where needed.

False confidence means probability >=0.8 with failure; false pessimism means
probability <=0.2 with success. Both objective and panel variants are recorded.
Paired improvement/regression compares identical task/seed/repetition; a missing
outcome is excluded, never treated as unchanged. Negative Brier/MAE delta is an
improvement. Positive score delta is an improvement.

## Interventions and interpretation

`feedback` passes individual baseline judge verdicts to the revision agent, not
the objective answer key. `self_critique` uses only the baseline answer, public
task and tool evidence. `none` records baseline only. Intervention kind, version,
text and provenance are saved on the revision and in its trace.

The included three-rubric panel deliberately creates a conflict: exposition
rewards explanation even when tasks request terse answers. A real experiment
should justify rubric choices in advance. Reusing one provider/model does not
create independent errors. Revision gains can reflect additional compute, answer
exposure or regression to the mean; this demonstration is not a causal study.
