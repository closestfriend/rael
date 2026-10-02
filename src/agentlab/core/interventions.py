"""Explicit stage-crossing inputs. Neither intervention exposes the answer key."""

import json

from agentlab.core.models import InterventionRecord, Message, Run
from agentlab.providers.session import ModelSession


class FeedbackIntervention:
    def create(self, baseline: Run) -> InterventionRecord:
        feedback = [v.model_dump() for v in baseline.verdicts if v.status == "ok"]
        return InterventionRecord(
            kind="feedback",
            source_run_id=baseline.id,
            text="Review these independent judge assessments, then revise your answer. They may be wrong.\n"
            + json.dumps(feedback),
            provenance=[
                f"{v.evaluator_id}@{v.version}" for v in baseline.verdicts if v.status == "ok"
            ],
        )


class SelfCritiqueIntervention:
    def __init__(self, session: ModelSession):
        self.session = session

    def create(self, baseline: Run) -> InterventionRecord:
        payload = {
            "task": baseline.task.public().model_dump(),
            "answer": baseline.answer,
            "tool_evidence": [e.data for e in baseline.trace if e.type == "tool_result"],
        }
        result = self.session.call(
            [
                Message(
                    role="system",
                    content="Identify brief, observable weaknesses in this answer and checks to perform before revision. Do not provide private reasoning. No evaluator feedback is available.",
                ),
                Message(role="user", content=json.dumps(payload)),
            ],
            purpose="critique",
        )
        if not result.message.content:
            raise ValueError("Self-critique returned no content")
        return InterventionRecord(
            kind="self_critique",
            source_run_id=baseline.id,
            text=result.message.content,
            provenance=["public task", "baseline answer", "tool observations"],
        )
