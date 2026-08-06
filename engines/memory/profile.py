"""UserProfile — the persistent 'who the user is + how to treat them' context.

Unlike ordinary memories (retrieved by relevance, expire after 12 days), the
profile is always-on: it is injected into every reasoning/generation call so
ORIGAMI answers as someone who knows the user. Stored as human-editable markdown
at ~/.origami/profile.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


class UserProfile:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else Path.home() / ".origami" / "profile.md"

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> str:
        try:
            return self.path.read_text().strip() if self.path.exists() else ""
        except Exception:
            return ""

    def save(self, text: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(text.strip() + "\n")
