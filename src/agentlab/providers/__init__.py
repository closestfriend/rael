"""Model-specific adapters live here, not in the research core."""

from agentlab.core.models import ModelConfig
from agentlab.core.protocols import Provider


def make_provider(config: ModelConfig) -> Provider:
    if config.provider == "mock":
        from agentlab.providers.mock import MockProvider

        return MockProvider()
    from agentlab.providers.openai import OpenAIProvider

    return OpenAIProvider(config)
