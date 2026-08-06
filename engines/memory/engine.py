"""MemoryEngine — structured long-term memory. JSON-backed first (interface-
compatible with a vector DB later, per the vision's "no vector DB yet").

Retrieval is keyword-relevance for now (rank by shared words + tag/kind hits).
Swapping in embeddings later means only changing `search()`, not callers.
"""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from core.schemas.memory import MemoryRecord

DEFAULT_EXPIRE_DAYS = 12  # ordinary memories fade; important ones never do

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "to", "of", "and", "or", "is", "are", "i", "my", "me",
         "you", "your", "it", "that", "this", "in", "on", "for", "with", "about",
         "what", "do", "know", "am", "was", "were", "be", "as", "at"}


def _tokens(text: str) -> set:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 1}


class MemoryEngine(ABC):
    @abstractmethod
    def add(self, text: str, kind: str = "fact", tags: Optional[List[str]] = None,
            important: bool = False) -> MemoryRecord: ...

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
    """Facts persisted to JSON. Ordinary memories live in memory.json and expire
    after `expire_days`; important ones live in memory-important.json and never
    expire (a separate, permanent store)."""

    def __init__(self, path: Optional[Path] = None,
                 expire_days: int = DEFAULT_EXPIRE_DAYS) -> None:
        self.path = Path(path) if path else Path.home() / ".origami" / "memory.json"
        self.important_path = self.path.with_name(self.path.stem + "-important.json")
        self.expire_days = expire_days
        self._records = self._load(self.path)
        self._important = self._load(self.important_path)
        self._prune()

    @staticmethod
    def _load(path: Path) -> List[MemoryRecord]:
        if not path.exists():
            return []
        try:
            return [MemoryRecord.from_dict(d) for d in json.loads(path.read_text())]
        except Exception:
            return []

    @staticmethod
    def _save(path: Path, records: List[MemoryRecord]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([r.to_dict() for r in records], indent=2))

    def _prune(self) -> None:
        """Drop ordinary memories older than expire_days (important never expire)."""
        cutoff = time.time() - self.expire_days * 86400
        kept = [r for r in self._records if r.created_at >= cutoff]
        if len(kept) != len(self._records):
            self._records = kept
            self._save(self.path, self._records)

    def add(self, text: str, kind: str = "fact", tags: Optional[List[str]] = None,
            important: bool = False) -> MemoryRecord:
        important = important or kind == "important"
        record = MemoryRecord(text=text.strip(),
                              kind="important" if important else kind, tags=tags or [])
        if important:
            self._important.append(record)
            self._save(self.important_path, self._important)
        else:
            self._records.append(record)
            self._save(self.path, self._records)
        return record

    def all(self) -> List[MemoryRecord]:
        return self._important + self._records

    def search(self, query: str, limit: int = 5) -> List[MemoryRecord]:
        q = _tokens(query)
        if not q:
            return []
        scored = []
        for r in self.all():
            overlap = len(q & _tokens(r.text))
            overlap += sum(1 for tag in r.tags if tag.lower() in q)
            if r.kind == "important":
                overlap += 1  # important memories rank a touch higher
            if overlap:
                scored.append((overlap, -r.created_at, r))
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        return [r for _, _, r in scored[:limit]]
