import json
from pathlib import Path

from agentlab.core.models import Task


class JsonTaskAdapter:
    def load(self, source: str) -> list[Task]:
        raw = json.loads(Path(source).read_text(encoding="utf-8"))
        if not isinstance(raw, list) or not raw:
            raise ValueError("Task file must contain a nonempty JSON array")
        tasks = [Task.model_validate(item) for item in raw]
        if len({task.id for task in tasks}) != len(tasks):
            raise ValueError("Task IDs must be unique")
        return tasks
