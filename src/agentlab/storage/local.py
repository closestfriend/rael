"""JSON is the source of truth; SQLite is a relocatable lookup index."""

import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path

from agentlab.core.models import Experiment, Run


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Store:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "index.sqlite3"
        with sqlite3.connect(self.db) as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, path TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, path TEXT NOT NULL);
            """)

    def directory(self, experiment_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", experiment_id):
            raise ValueError("Invalid experiment ID")
        return self.root / experiment_id

    def start(self, experiment: Experiment):
        directory = self.directory(experiment.id)
        directory.mkdir(exist_ok=False)
        write_json(directory / "config.json", experiment.config.model_dump(mode="json"))
        write_json(directory / "tasks.json", [t.model_dump(mode="json") for t in experiment.tasks])
        write_json(directory / "manifest.json", experiment.manifest)
        self.save(experiment)

    def save_run(self, run: Run):
        path = self.directory(run.experiment_id) / "runs" / f"{run.id}.json"
        write_json(path, run.model_dump(mode="json"))
        with sqlite3.connect(self.db) as db:
            db.execute(
                "INSERT OR REPLACE INTO runs VALUES (?, ?, ?)",
                (run.id, run.experiment_id, str(path.relative_to(self.root))),
            )

    def save(self, experiment: Experiment):
        path = self.directory(experiment.id) / "result.json"
        write_json(path, experiment.model_dump(mode="json"))
        with sqlite3.connect(self.db) as db:
            db.execute(
                "INSERT OR REPLACE INTO experiments VALUES (?, ?, ?)",
                (experiment.id, str(path.relative_to(self.root)), experiment.status),
            )

    def get_experiment(self, experiment_id: str) -> Experiment:
        return Experiment.model_validate_json(
            (self.directory(experiment_id) / "result.json").read_text()
        )

    def get_run(self, run_id: str) -> Run:
        with sqlite3.connect(self.db) as db:
            row = db.execute("SELECT path FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            raise ValueError(f"Unknown run: {run_id}")
        path = (self.root / row[0]).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Run index points outside the results directory")
        return Run.model_validate_json(path.read_text())
