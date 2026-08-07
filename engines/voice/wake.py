"""Wake Engine — every way ORIGAMI can be summoned.

Triggers are pluggable so a wake word, a finger snap, a keyboard shortcut, the
dashboard button or (later) a hardware button all arrive through one path. The
always-available triggers work today; acoustic ones activate when their optional
dependency is installed.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class Trigger(str, Enum):
    WAKE_WORD = "wake_word"
    SNAP = "finger_snap"
    HOTKEY = "hotkey"
    DASHBOARD = "dashboard"
    CLI = "cli"
    HARDWARE = "hardware"   # reserved: robot button, wearable, IoT


@dataclass
class WakeEvent:
    trigger: Trigger
    confidence: float = 1.0
    detail: str = ""


class WakeSource(ABC):
    trigger: Trigger

    @abstractmethod
    def wait(self, timeout: Optional[float] = None) -> Optional[WakeEvent]:
        """Block until this source fires (or timeout)."""

    def is_available(self) -> bool:
        return True

    def install_hint(self) -> str:
        return ""


class ManualWake(WakeSource):
    """CLI / dashboard / hotkey — always available, <1ms."""
    trigger = Trigger.CLI

    def wait(self, timeout: Optional[float] = None) -> Optional[WakeEvent]:
        return WakeEvent(self.trigger, detail="manual")


class WakeWordSource(WakeSource):
    """'Hey ORIGAMI' via openWakeWord (custom words supported later).

        pip install openwakeword
    """
    trigger = Trigger.WAKE_WORD

    def __init__(self, phrase: Optional[str] = None) -> None:
        self.phrase = phrase or os.getenv("ORIGAMI_WAKE_WORD", "hey origami")
        self._model = None

    def is_available(self) -> bool:
        try:
            import openwakeword  # noqa: F401
            import sounddevice   # noqa: F401
            return True
        except Exception:
            return False

    def install_hint(self) -> str:
        return "pip install openwakeword sounddevice"

    def wait(self, timeout: Optional[float] = None) -> Optional[WakeEvent]:
        if not self.is_available():
            return None
        import numpy as np
        import sounddevice as sd
        from openwakeword.model import Model

        if self._model is None:
            self._model = Model()
        block = 1280  # 80ms @16k, what the model expects
        with sd.InputStream(samplerate=16000, channels=1, dtype="int16",
                            blocksize=block) as stream:
            waited = 0.0
            while timeout is None or waited < timeout:
                data, _ = stream.read(block)
                scores = self._model.predict(np.squeeze(data))
                for name, score in scores.items():
                    if score > 0.5:
                        return WakeEvent(self.trigger, confidence=float(score), detail=name)
                waited += block / 16000
        return None


class SnapSource(WakeSource):
    """Finger-snap activation — a sharp transient above the noise floor.

    Deliberately conservative: a snap is a very short, very loud spike, so we
    require a high peak with low surrounding energy to avoid false fires.
    """
    trigger = Trigger.SNAP

    def __init__(self, peak: float = 0.35) -> None:
        self.peak = peak

    def is_available(self) -> bool:
        try:
            import sounddevice  # noqa: F401
            return True
        except Exception:
            return False

    def install_hint(self) -> str:
        return "pip install sounddevice"

    def wait(self, timeout: Optional[float] = None) -> Optional[WakeEvent]:
        if not self.is_available():
            return None
        import numpy as np
        import sounddevice as sd
        block = 512
        with sd.InputStream(samplerate=16000, channels=1, dtype="float32",
                            blocksize=block) as stream:
            waited = 0.0
            while timeout is None or waited < timeout:
                data, _ = stream.read(block)
                a = np.abs(data)
                if float(a.max()) > self.peak and float(a.mean()) < self.peak * 0.18:
                    return WakeEvent(self.trigger, confidence=float(a.max()), detail="snap")
                waited += block / 16000
        return None


class WakeEngine:
    """Owns every trigger. `sources()` reports what is live vs installable."""

    def __init__(self, sources: Optional[List[WakeSource]] = None) -> None:
        self.sources = sources or [WakeWordSource(), SnapSource(), ManualWake()]

    def trigger_now(self, trigger: Trigger = Trigger.CLI, detail: str = "") -> WakeEvent:
        return WakeEvent(trigger, detail=detail)

    def acoustic(self) -> List[WakeSource]:
        return [s for s in self.sources if s.trigger in (Trigger.WAKE_WORD, Trigger.SNAP)]

    def status(self) -> List[dict]:
        return [{"trigger": s.trigger.value, "available": s.is_available(),
                 "install": "" if s.is_available() else s.install_hint(),
                 "phrase": getattr(s, "phrase", None)} for s in self.sources]
