"""Enrolled identity — the voice profile ORIGAMI checks activations against.

Privacy-first: only the derived embedding is stored (~40 floats), never raw
audio, unless the user explicitly opts in. Lives at ~/.origami/identity.json
with owner-only permissions.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.persist import atomic_write_json, read_text

DEFAULT_WAKE_PHRASE = "i am iron man"


@dataclass
class VoiceProfile:
    name: str = "owner"
    embeddings: List[List[float]] = field(default_factory=list)  # several enrolments
    verifier: str = ""                # which verifier produced them
    threshold: float = 0.80           # configurable confidence
    wake_phrase: str = DEFAULT_WAKE_PHRASE
    language: str = "en"
    speech_rate: int = 190
    keep_audio: bool = False          # raw audio is never kept unless enabled
    enrolled_at: float = field(default_factory=time.time)
    samples: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VoiceProfile":
        from dataclasses import fields
        return cls(**{f.name: d[f.name] for f in fields(cls) if f.name in d})


class IdentityStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else Path.home() / ".origami" / "identity.json"

    def load(self) -> Optional[VoiceProfile]:
        raw = read_text(self.path)
        if not raw:
            return None
        try:
            return VoiceProfile.from_dict(json.loads(raw))
        except Exception:
            return None

    def save(self, profile: VoiceProfile) -> None:
        atomic_write_json(self.path, profile.to_dict())
        try:
            os.chmod(self.path, 0o600)   # owner-only
        except OSError:
            pass

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def exists(self) -> bool:
        return self.path.exists()


class AttemptLog:
    """Failed attempts are logged locally (never with personal data attached)."""

    def __init__(self, path: Optional[Path] = None, limit: int = 200) -> None:
        self.path = Path(path) if path else Path.home() / ".origami" / "auth-log.json"
        self.limit = limit

    def record(self, ok: bool, method: str, confidence: float, reason: str = "") -> None:
        entries = self.recent(self.limit)
        entries.append({"at": time.time(), "ok": bool(ok), "method": method,
                        "confidence": round(float(confidence), 3), "reason": reason})
        atomic_write_json(self.path, entries[-self.limit:])

    def recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        raw = read_text(self.path)
        if not raw:
            return []
        try:
            return json.loads(raw)[-limit:]
        except Exception:
            return []

    def recent_failures(self, within_seconds: float = 300) -> int:
        cutoff = time.time() - within_seconds
        return sum(1 for e in self.recent(self.limit)
                   if not e.get("ok") and e.get("at", 0) >= cutoff)
