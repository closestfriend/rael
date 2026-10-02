"""Small structural contracts; integrations need not inherit framework classes."""

from typing import Any, Protocol

from agentlab.core.models import (
    Completion,
    CompletionRequest,
    InterventionRecord,
    Message,
    Prediction,
    PublicTask,
    Run,
    Task,
    ToolSpec,
    Verdict,
)


class Provider(Protocol):
    def complete(self, request: CompletionRequest) -> Completion: ...


class Tool(Protocol):
    spec: ToolSpec

    def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]: ...


class Agent(Protocol):
    def attempt(
        self,
        task: PublicTask,
        intervention: InterventionRecord | None = None,
        previous_answer: str | None = None,
    ) -> tuple[str, list[Message]]: ...

    def predict(self, messages: list[Message], criteria: list[dict[str, Any]]) -> Prediction: ...


class Evaluator(Protocol):
    def evaluate(
        self, task: PublicTask, answer: str, evidence: list[dict[str, Any]]
    ) -> Verdict: ...


class Intervention(Protocol):
    def create(self, baseline: Run) -> InterventionRecord: ...


class TaskAdapter(Protocol):
    def load(self, source: str) -> list[Task]: ...
