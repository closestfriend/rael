"""Observable calls and retries shared by agents and judges."""

import time

from agentlab.core.models import Completion, CompletionRequest, Message, ModelConfig, ToolSpec
from agentlab.core.protocols import Provider
from agentlab.core.traces import Recorder


class ProviderError(RuntimeError):
    def __init__(
        self, message: str, *, retryable: bool = False, observed_response: dict | None = None
    ):
        super().__init__(message)
        self.retryable = retryable
        self.observed_response = observed_response


class ModelSession:
    def __init__(self, provider: Provider, config: ModelConfig, recorder: Recorder, seed: int):
        self.provider, self.config, self.recorder, self.seed = provider, config, recorder, seed

    def call(
        self,
        messages: list[Message],
        *,
        purpose: str,
        tools: list[ToolSpec] | None = None,
        json_output: bool = False,
    ) -> Completion:
        request = CompletionRequest(
            messages=messages,
            tools=tools or [],
            json_output=json_output,
            purpose=purpose,
            seed=self.seed,
        )
        for attempt in range(self.config.max_retries + 1):
            call_id = f"{self.recorder.run_id}-call-{len(self.recorder.events)}"
            self.recorder.emit(
                "model_call",
                purpose,
                call_id=call_id,
                attempt=attempt,
                request=request.model_dump(mode="json"),
                config=self.config.model_dump(),
            )
            start = time.perf_counter()
            try:
                response = self.provider.complete(request)
            except Exception as exc:
                # Never serialize arbitrary exception strings: HTTP transports may echo secrets.
                safe = (
                    str(exc)
                    if isinstance(exc, ProviderError)
                    else f"Provider failed ({type(exc).__name__})"
                )
                latency = (time.perf_counter() - start) * 1000
                if isinstance(exc, ProviderError) and exc.observed_response is not None:
                    self.recorder.emit(
                        "model_result",
                        purpose,
                        call_id=call_id,
                        response=exc.observed_response,
                        invalid=True,
                        latency_ms=latency,
                    )
                    latency = 0
                self.recorder.emit(
                    "error", purpose, call_id=call_id, error=safe, latency_ms=latency
                )
                if (
                    isinstance(exc, ProviderError)
                    and exc.retryable
                    and attempt < self.config.max_retries
                ):
                    self.recorder.emit(
                        "retry", purpose, previous_call_id=call_id, next_attempt=attempt + 1
                    )
                    time.sleep(0.1 * 2**attempt)
                    continue
                raise ProviderError(safe) from exc
            self.recorder.emit(
                "model_result",
                purpose,
                call_id=call_id,
                response=response.model_dump(mode="json"),
                latency_ms=(time.perf_counter() - start) * 1000,
            )
            return response
        raise AssertionError("Retry loop exhausted without a result")
