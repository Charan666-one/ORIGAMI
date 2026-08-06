"""MemoryEngine — structured long-term memory. JSON-backed first (interface-
compatible with a vector DB later, per the vision's "no vector DB yet").

Retrieval is keyword-relevance for now (rank by shared words + tag/kind hits).
Swapping in embeddings later means only changing `search()`, not callers.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from core.schemas.memory import MemoryRecord

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "to", "of", "and", "or", "is", "are", "i", "my", "me",
         "you", "your", "it", "that", "this", "in", "on", "for", "with", "about",
         "what", "do", "know", "am", "was", "were", "be", "as", "at"}


def _tokens(text: str) -> set:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1}


class MemoryEngine(ABC):
    @abstractmethod
    def add(self, text: str, kind: str = "fact", tags: Optional[List[str]] = None) -> MemoryRecord: ...

    @abstractmethod
    def all(self) -> List[MemoryRecord]: ...

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> List[MemoryRecord]: ...

    def context_for(self, query: str, limit: int = 5) -> str:
        """A compact bullet list of relevant memories to prepend to a brain prompt."""
        hits = self.search(query, limit=limit)
        if not hits:
            return ""
        return "\n".join(f"- {r.text}" for r in hits)


class JSONMemory(MemoryEngine):
    """Facts persisted to a JSON file (default ~/.origami/memory.json)."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else Path.home() / ".origami" / "memory.json"
        self._records: List[MemoryRecord] = self._load()

    def _load(self) -> List[MemoryRecord]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
            return [MemoryRecord.from_dict(d) for d in data]
        except Exception:
            return []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([r.to_dict() for r in self._records], indent=2))

    def add(self, text: str, kind: str = "fact", tags: Optional[List[str]] = None) -> MemoryRecord:
        record = MemoryRecord(text=text.strip(), kind=kind, tags=tags or [])
        self._records.append(record)
        self._save()
        return record

    def all(self) -> List[MemoryRecord]:
        return list(self._records)

    def search(self, query: str, limit: int = 5) -> List[MemoryRecord]:
        q = _tokens(query)
        if not q:
            return []
        scored = []
        for r in self._records:
            overlap = len(q & _tokens(r.text))
            overlap += sum(1 for tag in r.tags if tag.lower() in q)  # tag hits count
            if overlap:
                scored.append((overlap, -r.created_at, r))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [r for _, _, r in scored[:limit]]
