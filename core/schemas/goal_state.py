"""Long-running goals — the state behind Goal Mode.

Distinct from `core.schemas.goal.Goal` (a single request): a GoalState is a
multi-step objective ORIGAMI tracks over days ("get a Google internship"),
broken into milestones it can report progress on.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Milestone:
    text: str
    done: bool = False

    def to_dict(self) -> dict:
        return {"text": self.text, "done": self.done}

    @classmethod
    def from_dict(cls, d: dict) -> "Milestone":
        return cls(text=d["text"], done=bool(d.get("done", False)))


@dataclass
class GoalState:
    title: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    milestones: List[Milestone] = field(default_factory=list)
    status: str = "active"  # active | achieved | abandoned
    created_at: float = field(default_factory=time.time)

    def progress(self) -> Tuple[int, int]:
        done = sum(1 for m in self.milestones if m.done)
        return done, len(self.milestones)

    def next_open(self) -> List[Milestone]:
        return [m for m in self.milestones if not m.done]

    def to_dict(self) -> dict:
        return {"title": self.title, "id": self.id, "status": self.status,
                "created_at": self.created_at,
                "milestones": [m.to_dict() for m in self.milestones]}

    @classmethod
    def from_dict(cls, d: dict) -> "GoalState":
        return cls(title=d["title"], id=d.get("id", uuid.uuid4().hex[:8]),
                   status=d.get("status", "active"),
                   created_at=d.get("created_at", time.time()),
                   milestones=[Milestone.from_dict(m) for m in d.get("milestones", [])])
