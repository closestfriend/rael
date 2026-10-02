"""Deliberately scripted fixture. This is not a model or a benchmark result.

Answers are private to this fixture adapter, never injected into task prompts.
Only bundled task IDs are supported. Actual grading happens in the harness.
"""

import json

from agentlab.core.models import Completion, CompletionRequest, Message, ToolCall, Usage
from agentlab.core.tools import Calculator
from agentlab.providers.session import ProviderError

ANSWERS = {
    "capital": ("Sydney", "Canberra"),
    "terse": ("Paris", "Paris"),
    "bat-ball": ("The ball costs $0.10, because $1.10 minus $1.00 is $0.10.", "0.05"),
    "json-only": ('Here is the answer: {"ok": true}', '{"ok": true}'),
    "unit": ("1000", "100"),
    "reverse": ("reward", "reward"),
    "uncertainty": ("The launch date is October 12.", "INSUFFICIENT EVIDENCE"),
    "rounding": ("3.14", "3.14"),
    "negation": ("Yes, whales are fish because they live in water.", "No"),
    "evidence": ("The trial had 240 participants [S1].", "The trial had 240 participants [S1]."),
}


def task_payload(request):
    for message in request.messages:
        if message.role == "user" and message.content:
            try:
                value = json.loads(message.content)
                if isinstance(value, dict) and "task" in value:
                    return value
            except ValueError:
                pass
    raise ProviderError("Scripted provider needs a structured task payload")


class MockProvider:
    def complete(self, request: CompletionRequest) -> Completion:
        payload = task_payload(request)
        task = payload["task"]
        revised = bool(payload.get("intervention"))
        task_id = task["id"]
        content = None
        calls = []
        if request.purpose == "answer":
            tool_messages = [m for m in request.messages if m.role == "tool"]
            tool = (
                "calculator"
                if task_id in {"multiply", "tool-required"}
                else "search"
                if task_id == "evidence"
                else None
            )
            if tool and not tool_messages and any(t.name == tool for t in request.tools):
                args = (
                    {"expression": task["context"]["expression"]}
                    if tool == "calculator"
                    else {"query": "trial"}
                )
                calls = [ToolCall(id="fixture-call-1", name=tool, arguments=args)]
            elif tool == "calculator" and tool_messages:
                result = json.loads(tool_messages[-1].content)
                content = str(result["result"]["value"])
            elif task_id in ANSWERS:
                content = ANSWERS[task_id][int(revised)]
            else:
                raise ProviderError(f"Scripted fixture does not support task '{task_id}'")
        elif request.purpose == "prediction":
            p = 0.2 if task_id == "terse" else 0.9 if not revised else 0.8
            content = json.dumps(
                {
                    "pass_probability": p,
                    "predicted_score": p,
                    "confidence": p,
                    "likely_failure_dimensions": ["instruction_following"],
                    "weak_points": ["Scripted prediction for pipeline demonstration."],
                }
            )
        elif request.purpose == "critique":
            content = "Check facts, obey the exact requested output format, and verify calculations with tools."
        elif request.purpose == "pairwise":
            content = json.dumps(
                {
                    "winner": "tie",
                    "confidence": 0.5,
                    "rationale": "Scripted pairwise fixture; no model inference.",
                }
            )
        elif request.purpose == "judge":
            answer = payload["answer"].strip()
            expected = {
                "capital": "Canberra",
                "terse": "Paris",
                "bat-ball": "0.05",
                "unit": "1000",
                "reverse": "reward",
                "uncertainty": "INSUFFICIENT EVIDENCE",
                "rounding": "3.14",
                "negation": "No",
                "json-only": '{"ok": true}',
            }
            if task_id in {"multiply", "tool-required"}:
                correct = (
                    float(answer)
                    == Calculator().invoke({"expression": task["context"]["expression"]})["value"]
                )
            elif task_id == "evidence":
                correct = "240" in answer and "[S1]" in answer
            else:
                correct = answer == expected.get(task_id)
            rubric = payload.get("rubric", "").lower()
            if "explanation" in rubric:
                score = 0.9 if len(answer.split()) >= 6 else 0.2
            elif "instruction" in rubric and task_id == "bat-ball":
                score = 1.0 if answer == "0.05" else 0.0
            else:
                score = 1.0 if correct else 0.0
            content = json.dumps(
                {
                    "score": score,
                    "confidence": 1.0,
                    "rationale": "Deterministic fixture judgment under this rubric.",
                    "dimensions": {"criterion": score},
                    "evidence": [answer],
                }
            )
        return Completion(
            message=Message(role="assistant", content=content, tool_calls=calls),
            model="scripted-v1",
            provider="mock",
            usage=Usage(input_tokens=0, output_tokens=0, cost_usd=0, cost_source="offline fixture"),
            metadata={"synthetic": True, "fixture_version": "1"},
        )
