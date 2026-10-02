"""Pure metrics with coverage; missing observations are never coerced to zero."""

from itertools import combinations
from statistics import mean
from typing import Any

from agentlab.core.models import Run


def average(values):
    present = [v for v in values if v is not None]
    return mean(present) if present else None


def complete_sum(values):
    return sum(values) if all(v is not None for v in values) else None


def run_metrics(run: Run, expected_judges: int) -> dict[str, Any]:
    verdicts = [
        v
        for v in run.verdicts
        if v.status == "ok" and v.kind != "human" and v.score is not None and v.passed is not None
    ]
    scores = [v.score for v in verdicts]
    complete = len(verdicts) == expected_judges and expected_judges > 0
    panel_passed = (sum(v.passed for v in verdicts) > expected_judges / 2) if complete else None
    predicted = run.prediction
    objective = run.objective.passed if run.objective and run.objective.status == "ok" else None
    pairs = list(combinations(verdicts, 2))
    calls = [e for e in run.trace if e.type == "model_call"]
    results = [e for e in run.trace if e.type == "model_result"]
    usage = {e.data["call_id"]: e.data["response"]["usage"] for e in results}
    costs = [usage.get(e.data["call_id"], {}).get("cost_usd") for e in calls]
    tokens = [
        complete_sum(
            [
                usage.get(e.data["call_id"], {}).get("input_tokens"),
                usage.get(e.data["call_id"], {}).get("output_tokens"),
            ]
        )
        for e in calls
    ]
    tool_results = [e for e in run.trace if e.type == "tool_result"]
    judge_mean = average(scores)
    return {
        "objective_passed": objective,
        "judge_mean_score": judge_mean,
        "judge_pass_rate": average([int(v.passed) for v in verdicts]),
        "judge_coverage": len(verdicts) / expected_judges if expected_judges else None,
        "judges_scored": len(verdicts),
        "judges_expected": expected_judges,
        "panel_passed": panel_passed,
        "judge_disagreement": average([int(a.passed != b.passed) for a, b in pairs]),
        "judge_score_spread": max(scores) - min(scores) if scores else None,
        "panel_brier": (predicted.pass_probability - int(panel_passed)) ** 2
        if predicted and panel_passed is not None
        else None,
        "objective_brier": (predicted.confidence - int(objective)) ** 2
        if predicted and objective is not None
        else None,
        "score_mae": abs(predicted.predicted_score - judge_mean)
        if predicted and complete
        else None,
        "objective_false_confidence": predicted.confidence >= 0.8 and not objective
        if predicted and objective is not None
        else None,
        "objective_false_pessimism": predicted.confidence <= 0.2 and objective
        if predicted and objective is not None
        else None,
        "panel_false_confidence": predicted.pass_probability >= 0.8 and not panel_passed
        if predicted and panel_passed is not None
        else None,
        "panel_false_pessimism": predicted.pass_probability <= 0.2 and panel_passed
        if predicted and panel_passed is not None
        else None,
        "tool_calls": len(tool_results),
        "tool_errors": sum(not e.data["ok"] for e in tool_results),
        "tool_error_rate": average([int(not e.data["ok"]) for e in tool_results]),
        "model_calls": len(calls),
        "model_errors": sum(e.type == "error" and "call_id" in e.data for e in run.trace),
        "tokens": complete_sum(tokens),
        "known_tokens": sum(t for t in tokens if t is not None),
        "token_coverage": sum(t is not None for t in tokens) / len(tokens) if tokens else 1,
        "cost_usd": complete_sum(costs),
        "known_cost_usd": sum(c for c in costs if c is not None),
        "cost_coverage": sum(c is not None for c in costs) / len(costs) if costs else 1,
        "latency_ms": sum(
            e.data.get("latency_ms", 0)
            for e in run.trace
            if e.type in {"model_result", "error", "tool_result"}
        ),
    }


def compare_runs(before: Run, after: Run) -> dict[str, Any]:
    if (
        before.task.id != after.task.id
        or before.seed != after.seed
        or before.repetition != after.repetition
    ):
        raise ValueError("Compare runs for the same task, seed and repetition")
    a, b = before.metrics, after.metrics

    def delta(key):
        return b[key] - a[key] if a.get(key) is not None and b.get(key) is not None else None

    objective_pair = a.get("objective_passed") is not None and b.get("objective_passed") is not None
    full_panel = a.get("judge_coverage") == b.get("judge_coverage") == 1
    return {
        "before": before.id,
        "after": after.id,
        "task_id": before.task.id,
        "objective_improved": not a["objective_passed"] and b["objective_passed"]
        if objective_pair
        else None,
        "objective_regressed": a["objective_passed"] and not b["objective_passed"]
        if objective_pair
        else None,
        "score_delta": delta("judge_mean_score") if full_panel else None,
        "panel_brier_delta": delta("panel_brier"),
        "objective_brier_delta": delta("objective_brier"),
        "score_mae_delta": delta("score_mae"),
    }


def experiment_metrics(runs: list[Run]) -> dict[str, Any]:
    stages = {}
    for stage in ("baseline", "revision"):
        group = [r for r in runs if r.stage == stage]
        graded = [r for r in group if r.metrics.get("objective_passed") is not None]
        eligible = [r for r in group if r.task.grader and r.task.ground_truth is not None]
        complete_panels = [r for r in group if r.metrics.get("panel_passed") is not None]
        stages[stage] = {
            "attempts": len(group),
            "completed": sum(r.status == "completed" for r in group),
            "failed_or_partial": sum(r.status in {"partial", "failed"} for r in group),
            "objectively_graded": len(graded),
            "objective_eligible": len(eligible),
            "complete_panels": len(complete_panels),
            "objective_success_rate": average([int(r.metrics["objective_passed"]) for r in graded]),
            "objective_success_per_eligible_attempt": sum(
                bool(r.metrics.get("objective_passed")) for r in eligible
            )
            / len(eligible)
            if eligible
            else None,
            "panel_pass_rate": average([int(r.metrics["panel_passed"]) for r in complete_panels]),
        }
        for key in (
            "judge_mean_score",
            "judge_pass_rate",
            "judge_disagreement",
            "judge_coverage",
            "panel_brier",
            "objective_brier",
            "score_mae",
            "objective_false_confidence",
            "objective_false_pessimism",
            "panel_false_confidence",
            "panel_false_pessimism",
        ):
            values = [r.metrics.get(key) for r in group]
            stages[stage][key] = average(values)
            stages[stage][f"{key}_n"] = sum(v is not None for v in values)
    by_id = {r.id: r for r in runs}
    pairs = [compare_runs(by_id[r.parent_id], r) for r in runs if r.parent_id in by_id]
    cost = complete_sum([r.metrics.get("cost_usd") for r in runs])
    tool_calls = sum(r.metrics.get("tool_calls", 0) for r in runs)
    return {
        "stages": stages,
        "pairs": {
            "count": len(pairs),
            "objective_pairs": sum(p["objective_improved"] is not None for p in pairs),
            "scored_pairs": sum(p["score_delta"] is not None for p in pairs),
            "objective_improvement_rate": average([p["objective_improved"] for p in pairs]),
            "objective_regression_rate": average([p["objective_regressed"] for p in pairs]),
            "judge_improvement_rate": average(
                [p["score_delta"] > 0 if p["score_delta"] is not None else None for p in pairs]
            ),
            "judge_regression_rate": average(
                [p["score_delta"] < 0 if p["score_delta"] is not None else None for p in pairs]
            ),
            "mean_score_delta": average([p["score_delta"] for p in pairs]),
            "mean_panel_brier_delta": average([p["panel_brier_delta"] for p in pairs]),
            "mean_objective_brier_delta": average([p["objective_brier_delta"] for p in pairs]),
            "comparisons": pairs,
        },
        "resources": {
            "cost_usd": cost,
            "tokens": complete_sum([r.metrics.get("tokens") for r in runs]),
            "known_cost_usd": sum(r.metrics.get("known_cost_usd", 0) for r in runs),
            "known_tokens": sum(r.metrics.get("known_tokens", 0) for r in runs),
            "model_calls": sum(r.metrics.get("model_calls", 0) for r in runs),
            "latency_ms": sum(r.metrics.get("latency_ms", 0) for r in runs),
            "tool_error_rate": sum(r.metrics.get("tool_errors", 0) for r in runs) / tool_calls
            if tool_calls
            else None,
            "objective_successes_per_dollar": sum(
                r.metrics.get("objective_passed") is True for r in runs
            )
            / cost
            if cost
            else None,
        },
        "definitions": {
            "panel_pass": "Strict majority, only when all non-human panel members return scores",
            "disagreement": "Fraction of pairs of successful judges with different pass/fail verdicts",
            "confidence_thresholds": {"high": 0.8, "low": 0.2},
            "brier": "Mean squared probability error; smaller is better",
            "pairing": "Same task, seed, repetition; before and after feedback are not independent",
            "latency": "Sum of recorded model requests and tools, excluding orchestration and retry backoff",
        },
    }
