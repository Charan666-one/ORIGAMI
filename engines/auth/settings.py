"""Wake settings — the wake phrase is configuration, never code.

Stored at ~/.origami/wake.json so it can be changed at runtime ("change my wake
phrase to hey origami") without touching a single line of ORIGAMI.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Optional

from core.persist import atomic_write_json, read_text

DEFAULT_WAKE_PHRASE = "i am iron man"


@dataclass
class WakeSettings:
    wake_phrase: str = DEFAULT_WAKE_PHRASE
    wake_detector: str = "transcript"   # transcript | openwakeword | snap (future)
    confidence_threshold: float = 0.75  # speaker-verification cut-off
    enabled: bool = True                # master switch for passive listening
    session_timeout: float = 900.0      # seconds of inactivity before re-locking
    require_voice_match: bool = True    # phrase alone must never authenticate

    def to_dict(self) -> dict:
        return asdict(self)


class WakeSettingsStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else Path.home() / ".origami" / "wake.json"

    def load(self) -> WakeSettings:
        raw = read_text(self.path)
        if not raw:
            return WakeSettings()
        try:
            data = json.loads(raw)
            names = {f.name for f in fields(WakeSettings)}
            return WakeSettings(**{k: v for k, v in data.items() if k in names})
        except Exception:
            return WakeSettings()

    def save(self, settings: WakeSettings) -> None:
        atomic_write_json(self.path, settings.to_dict())

    def update(self, **changes) -> WakeSettings:
        settings = self.load()
        names = {f.name for f in fields(WakeSettings)}
        for key, value in changes.items():
            if key in names and value is not None:
                setattr(settings, key, value)
        if isinstance(settings.wake_phrase, str):
            settings.wake_phrase = settings.wake_phrase.lower().strip(" .,!?")
        self.save(settings)
        return settings
