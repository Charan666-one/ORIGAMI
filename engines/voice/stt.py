"""Speech recognition — offline-first, provider-independent.

Whisper (faster-whisper: the whisper.cpp-class CTranslate2 runtime) is the default
and runs entirely on-device. The interface takes audio *or* records from the mic,
so a streaming provider can be dropped in later without changing callers.

    pip install faster-whisper sounddevice
"""

from __future__ import annotations

import os
import queue
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

SAMPLE_RATE = 16000


@dataclass
class Transcript:
    text: str
    confidence: float = 1.0
    language: str = "en"
    seconds: float = 0.0


class SpeechRecognizer(ABC):
    name = "base"

    @abstractmethod
    def transcribe(self, audio) -> Transcript:
        """Transcribe a float32 mono 16kHz numpy array."""

    def is_available(self) -> bool:
        return True

    def install_hint(self) -> str:
        return ""


class WhisperSTT(SpeechRecognizer):
    """Local Whisper. `tiny`/`base` are the right sizes for an 8GB machine."""

    name = "whisper"

    def __init__(self, model_size: Optional[str] = None) -> None:
        self.model_size = model_size or os.getenv("ORIGAMI_WHISPER", "base.en")
        self._model = None

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except ImportError:
            return False

    def install_hint(self) -> str:
        return "pip install faster-whisper sounddevice"

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            # int8 keeps memory small; CPU is fine for tiny/base on Apple silicon
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    def transcribe(self, audio) -> Transcript:
        segments, info = self._load().transcribe(
            audio, language=None, vad_filter=True,          # noise / silence filtering
            beam_size=1, condition_on_previous_text=False)  # low latency
        text = " ".join(s.text.strip() for s in segments).strip()
        return Transcript(text=text, language=getattr(info, "language", "en"),
                          seconds=getattr(info, "duration", 0.0))


class Microphone:
    """Mic capture with simple silence detection (talk, pause, done)."""

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self.sample_rate = sample_rate

    def is_available(self) -> bool:
        try:
            import sounddevice  # noqa: F401
            return True
        except Exception:
            return False

    def record(self, max_seconds: float = 12.0, silence_seconds: float = 1.4,
               threshold: float = 0.012):
        """Record until the speaker stops, or max_seconds. Returns float32 audio."""
        import numpy as np
        import sounddevice as sd

        chunks: List = []
        q: "queue.Queue" = queue.Queue()
        block = int(self.sample_rate * 0.1)

        def cb(indata, frames, time_info, status):
            q.put(indata.copy())

        silent_for = 0.0
        spoke = False
        with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="float32",
                            blocksize=block, callback=cb):
            elapsed = 0.0
            while elapsed < max_seconds:
                try:
                    data = q.get(timeout=0.5)
                except queue.Empty:
                    continue
                chunks.append(data)
                elapsed += len(data) / self.sample_rate
                level = float(np.abs(data).mean())
                if level > threshold:
                    spoke, silent_for = True, 0.0
                else:
                    silent_for += len(data) / self.sample_rate
                    if spoke and silent_for >= silence_seconds:
                        break
        if not chunks:
            return None
        return np.concatenate(chunks, axis=0).flatten()


class RecognizerManager(SpeechRecognizer):
    """Picks the best available recognizer and owns the microphone."""

    name = "stt"

    def __init__(self, providers: Optional[List[SpeechRecognizer]] = None,
                 mic: Optional[Microphone] = None) -> None:
        self.providers = providers or [WhisperSTT()]
        self.mic = mic or Microphone()

    def active(self) -> Optional[SpeechRecognizer]:
        for p in self.providers:
            if p.is_available():
                return p
        return None

    def is_available(self) -> bool:
        return self.active() is not None and self.mic.is_available()

    def install_hint(self) -> str:
        return self.providers[0].install_hint() if self.providers else ""

    def transcribe(self, audio) -> Transcript:
        provider = self.active()
        if provider is None:
            return Transcript(text="", confidence=0.0)
        return provider.transcribe(audio)

    def listen(self, max_seconds: float = 12.0) -> Transcript:
        """Record from the mic and transcribe it."""
        if not self.is_available():
            return Transcript(text="", confidence=0.0)
        audio = self.mic.record(max_seconds=max_seconds)
        if audio is None or not len(audio):
            return Transcript(text="", confidence=0.0)
        return self.transcribe(audio)

    def status(self) -> dict:
        provider = self.active()
        return {"provider": provider.name if provider else None,
                "model": getattr(provider, "model_size", None),
                "mic": self.mic.is_available(),
                "available": self.is_available(),
                "install": self.install_hint() if not self.is_available() else ""}
