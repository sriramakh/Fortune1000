import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from config import PROGRESS_DIR

logger = logging.getLogger(__name__)


class ProgressTracker:
    def __init__(self, run_id: str, pipeline: str, total: int):
        PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
        self.file_path = PROGRESS_DIR / f"{pipeline}_run.json"
        self._load_or_create(run_id, pipeline, total)

    def _load_or_create(self, run_id: str, pipeline: str, total: int):
        if self.file_path.exists():
            with open(self.file_path) as f:
                self.data = json.load(f)
            # If previous run is done or it's a new run_id, start fresh
            if self.data.get("status") == "completed" or self.data.get("run_id") != run_id:
                self._create_new(run_id, pipeline, total)
        else:
            self._create_new(run_id, pipeline, total)

    def _create_new(self, run_id: str, pipeline: str, total: int):
        self.data = {
            "run_id": run_id,
            "pipeline": pipeline,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "total": total,
            "completed": [],
            "failed": {},
            "status": "in_progress",
        }
        self._save()

    @property
    def completed(self) -> set[str]:
        return set(self.data["completed"])

    @property
    def completed_count(self) -> int:
        return len(self.data["completed"])

    @property
    def failed_count(self) -> int:
        return len(self.data["failed"])

    def mark_completed(self, slug: str):
        if slug not in self.data["completed"]:
            self.data["completed"].append(slug)
            self._save()

    def mark_failed(self, slug: str, error: str, attempts: int):
        self.data["failed"][slug] = {
            "error": error,
            "attempts": attempts,
            "last_attempt": datetime.now(timezone.utc).isoformat(),
        }
        self._save()

    def finish(self):
        self.data["status"] = "completed"
        self.data["finished_at"] = datetime.now(timezone.utc).isoformat()
        self._save()

    def _save(self):
        with open(self.file_path, "w") as f:
            json.dump(self.data, f, indent=2)
