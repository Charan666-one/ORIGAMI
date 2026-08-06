"""UserProfile — the persistent 'who the user is + how to treat them' context.

Unlike ordinary memories (retrieved by relevance, expire after 12 days), the
profile is always-on: it is injected into every reasoning/generation call so
ORIGAMI answers as someone who knows the user. Stored as human-editable markdown
at ~/.origami/profile.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.persist import atomic_write_text, read_text


class UserProfile:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else Path.home() / ".origami" / "profile.md"

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> str:
        return read_text(self.path).strip()

    def save(self, text: str) -> None:
        atomic_write_text(self.path, text.strip() + "\n")
