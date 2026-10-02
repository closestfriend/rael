"""Write each observable event before continuing to the next stage."""

import json
import os
from pathlib import Path
from typing import Any

from agentlab.core.models import TraceEvent


class Recorder:
    def __init__(self, run_id: str, path: Path):
        self.run_id = run_id
        self.path = path
        self.events: list[TraceEvent] = []
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=False)

    def emit(self, event_type: str, phase: str, **data: Any) -> TraceEvent:
        event = TraceEvent(
            seq=len(self.events), run_id=self.run_id, phase=phase, type=event_type, data=data
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(event.model_dump(mode="json"), ensure_ascii=False, allow_nan=False)
                + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        self.events.append(event)
        return event
