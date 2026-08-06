"""Memory records — structured, queryable facts ORIGAMI keeps over time.

Not raw chat logs: each record is a single fact with a kind and tags so it can be
retrieved by relevance later (projects, preferences, people, decisions, notes).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import List


@dataclass
class MemoryRecord:
    text: str
    kind: str = "fact"       # fact | project | preference | person | decision | note
    tags: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"id": self.id, "text": self.text, "kind": self.kind,
                "tags": self.tags, "created_at": self.created_at}

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryRecord":
        return cls(text=d["text"], kind=d.get("kind", "fact"),
                   tags=d.get("tags", []), id=d.get("id", uuid.uuid4().hex[:12]),
                   created_at=d.get("created_at", time.time()))
