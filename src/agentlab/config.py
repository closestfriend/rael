import os
from pathlib import Path

import yaml

from agentlab.adapters.json_tasks import JsonTaskAdapter
from agentlab.core.models import ExperimentConfig, ModelConfig


def resolve_model(config: ModelConfig) -> ModelConfig:
    if config.base_url_env and os.getenv(config.base_url_env):
        return ModelConfig.model_validate(
            {**config.model_dump(), "base_url": os.environ[config.base_url_env]}
        )
    return config


def load_config(path: Path):
    path = path.resolve()
    config = ExperimentConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    config.agent = resolve_model(config.agent)
    for evaluator in config.evaluators:
        if evaluator.model:
            evaluator.model = resolve_model(evaluator.model)
    tasks = JsonTaskAdapter().load(str(path.parent / config.tasks))
    return config, tasks
