"""Scheduler — stores time-based reminders and answers "what's due now?".

JSON-backed (~/.origami/tasks.json). Also keeps a simple completion streak so the
monitor can encourage consistency.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Optional

from core.schemas.task import ScheduledTask

FOLLOW_UP_AFTER = 10 * 60  # seconds after due to ask "did you finish?"


class Scheduler:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else Path.home() / ".origami" / "tasks.json"
        self._tasks: List[ScheduledTask] = []
        self._streak = 0
        self._load()

    # --- persistence ------------------------------------------------------------

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            self._tasks = [ScheduledTask.from_dict(t) for t in data.get("tasks", [])]
            self._streak = data.get("streak", 0)
        except Exception:
            self._tasks, self._streak = [], 0

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {"tasks": [t.to_dict() for t in self._tasks], "streak": self._streak}, indent=2))

    # --- commands ---------------------------------------------------------------

    def add(self, text: str, due: float, important: bool = False) -> ScheduledTask:
        task = ScheduledTask(text=text.strip(), due=due, important=important)
        self._tasks.append(task)
        self._save()
        return task

    def pending(self) -> List[ScheduledTask]:
        return sorted((t for t in self._tasks if t.status == "pending"), key=lambda t: t.due)

    def all(self) -> List[ScheduledTask]:
        return list(self._tasks)

    @property
    def streak(self) -> int:
        return self._streak

    def mark_done(self, query: str) -> Optional[ScheduledTask]:
        task = self._match(query)
        if task is None:
            return None
        task.status = "done"
        self._streak += 1
        self._save()
        return task

    def _match(self, query: str) -> Optional[ScheduledTask]:
        q = query.lower().strip()
        for t in self._tasks:
            if t.status == "pending" and (q in t.text.lower() or t.id == q):
                return t
        return None

    # --- monitor loop queries ---------------------------------------------------

    def due_now(self, now: Optional[float] = None) -> List[ScheduledTask]:
        now = now or time.time()
        return [t for t in self._tasks
                if t.status == "pending" and not t.notified and t.due <= now]

    def needs_follow_up(self, now: Optional[float] = None) -> List[ScheduledTask]:
        now = now or time.time()
        return [t for t in self._tasks
                if t.status == "pending" and t.notified and not t.followed_up
                and now >= t.due + FOLLOW_UP_AFTER]

    def mark_notified(self, task: ScheduledTask) -> None:
        task.notified = True
        self._save()

    def mark_followed_up(self, task: ScheduledTask) -> None:
        task.followed_up = True
        self._save()
