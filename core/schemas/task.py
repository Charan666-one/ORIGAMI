"""ScheduledTask — a time-based reminder ORIGAMI monitors and follows up on."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class ScheduledTask:
    text: str
    due: float                       # epoch time it's due
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    status: str = "pending"          # pending | done | missed
    created_at: float = field(default_factory=time.time)
    notified: bool = False           # fired the "it's time" notification?
    followed_up: bool = False        # fired the "did you finish?" nudge?
    important: bool = False

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "ScheduledTask":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})
