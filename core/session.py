"""Session — per-conversation state. Thin in C1; grows with memory in C4."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List

from core.schemas.result import RunResult


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    history: List[RunResult] = field(default_factory=list)

    def record(self, result: RunResult) -> None:
        self.history.append(result)
