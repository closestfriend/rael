"""The portable experiment contract. All scores and probabilities use [0, 1]."""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}$")]


def now() -> str:
    return datetime.now(UTC).isoformat()


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)


class PublicTask(Schema):
    id: Identifier
    prompt: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    references: list[dict[str, Any]] = Field(default_factory=list)
    expected_output_type: str = "text"
    environment: str = "local"
    available_tools: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class Task(PublicTask):
    ground_truth: Any = None
    grader: Literal["exact", "numeric", "json", "contains"] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def public(self) -> PublicTask:
        return PublicTask.model_validate(self.model_dump(include=set(PublicTask.model_fields)))


class ToolSpec(Schema):
    name: str
    description: str
    parameters: dict[str, Any]


class ToolCall(Schema):
    id: str
    name: str
    arguments: dict[str, Any]


class Message(Schema):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None


class Usage(Schema):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    cost_source: str = "unknown"


class ModelConfig(Schema):
    provider: Literal["mock", "openai"] = "mock"
    model: str = "scripted-v1"
    base_url: str = "https://api.openai.com/v1"
    base_url_env: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int = Field(default=1200, ge=1, le=100000)
    timeout_seconds: float = Field(default=60, gt=0, le=600)
    max_retries: int = Field(default=1, ge=0, le=4)
    input_usd_per_million: float | None = Field(default=None, ge=0)
    output_usd_per_million: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def safe_endpoint(self):
        url = urlsplit(self.base_url)
        if (
            url.scheme not in {"http", "https"}
            or not url.netloc
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "base_url must be an HTTP(S) endpoint without credentials, query or fragment"
            )
        return self


class CompletionRequest(Schema):
    messages: list[Message]
    tools: list[ToolSpec] = Field(default_factory=list)
    json_output: bool = False
    purpose: Literal["answer", "prediction", "judge", "critique", "pairwise"] = "answer"
    seed: int = 0


class Completion(Schema):
    message: Message
    model: str
    provider: str
    usage: Usage = Field(default_factory=Usage)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceEvent(Schema):
    schema_version: str = "1.0"
    seq: int
    timestamp: str = Field(default_factory=now)
    run_id: str
    phase: str
    type: str
    data: dict[str, Any] = Field(default_factory=dict)


class Prediction(Schema):
    pass_probability: Probability
    predicted_score: Probability
    confidence: Probability
    likely_failure_dimensions: list[str] = Field(default_factory=list)
    weak_points: list[str] = Field(default_factory=list)


class JudgeOutput(Schema):
    score: Probability
    confidence: Probability
    rationale: str
    dimensions: dict[str, Probability] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)


class Verdict(Schema):
    evaluator_id: str
    version: str
    kind: str
    status: Literal["ok", "error", "pending"] = "ok"
    score: Probability | None = None
    passed: bool | None = None
    confidence: Probability | None = None
    rationale: str = ""
    dimensions: dict[str, Probability] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    error: str | None = None


class EvaluatorConfig(Schema):
    id: Identifier
    kind: Literal["rubric", "binary", "scalar", "human"] = "rubric"
    version: str = "1"
    rubric: str = "Assess correctness, instruction following and evidence."
    criterion: Literal["nonempty", "single_token", "tool_verified", "explanation"] = "nonempty"
    threshold: Probability = 0.5
    model: ModelConfig | None = None


class ExperimentConfig(Schema):
    name: Identifier
    tasks: str
    agent: ModelConfig = Field(default_factory=ModelConfig)
    evaluators: list[EvaluatorConfig] = Field(min_length=1)
    intervention: Literal["none", "feedback", "self_critique"] = "feedback"
    seeds: list[int] = Field(default_factory=lambda: [7], min_length=1)
    repetitions: int = Field(default=1, ge=1, le=100)
    max_tool_rounds: int = Field(default=4, ge=0, le=20)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({e.id for e in self.evaluators}) != len(self.evaluators):
            raise ValueError("Evaluator IDs must be unique")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("Seeds must be unique")
        if all(e.kind == "human" for e in self.evaluators):
            raise ValueError("At least one scoring evaluator is required")
        return self


class InterventionRecord(Schema):
    kind: str
    version: str = "1"
    source_run_id: str
    text: str
    provenance: list[str] = Field(default_factory=list)


class Run(Schema):
    id: Identifier
    experiment_id: Identifier
    task: Task
    seed: int
    repetition: int
    stage: Literal["baseline", "revision"]
    parent_id: str | None = None
    status: Literal["running", "completed", "partial", "failed"] = "running"
    started_at: str = Field(default_factory=now)
    finished_at: str | None = None
    answer: str | None = None
    prediction: Prediction | None = None
    objective: Verdict | None = None
    verdicts: list[Verdict] = Field(default_factory=list)
    intervention: InterventionRecord | None = None
    trace: list[TraceEvent] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class Experiment(Schema):
    schema_version: str = "1.0"
    id: Identifier
    name: str
    status: Literal["running", "completed", "partial"] = "running"
    created_at: str = Field(default_factory=now)
    finished_at: str | None = None
    config: ExperimentConfig
    tasks: list[Task]
    manifest: dict[str, Any] = Field(default_factory=dict)
    runs: list[Run] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
