"""Voice synthesis — provider-independent, offline-first, interruptible.

Same contract pattern as the Brain: `Synthesizer` is the interface, providers are
swappable, and the manager picks the best available one. Piper (local neural TTS)
is preferred when installed; macOS `say` is the always-available fallback.

Speech is interruptible: `stop()` kills the active utterance immediately, which is
what makes "stop / wait" feel natural mid-sentence.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class VoiceProfile:
    """A named voice. Emotion/rate/pitch are declared now so profiles, emotion-
    aware delivery and (later) cloning need no interface change."""
    name: str = "default"
    voice: str = ""          # provider-specific voice id
    rate: int = 190          # words per minute
    emotion: str = "neutral"  # neutral | warm | urgent  (reserved)


class Synthesizer(ABC):
    name = "base"

    @abstractmethod
    def speak(self, text: str, profile: Optional[VoiceProfile] = None) -> None:
        """Speak (blocking until finished or interrupted)."""

    def is_available(self) -> bool:
        return True

    def stop(self) -> None:
        """Interrupt the current utterance."""

    def voices(self) -> List[str]:
        return []


class MacSayTTS(Synthesizer):
    """macOS built-in speech — always available, natural, zero install."""

    name = "macos-say"

    def __init__(self, voice: str = "") -> None:
        self.voice = voice or os.getenv("ORIGAMI_VOICE", "Samantha")
        self._proc: Optional[subprocess.Popen] = None

    def is_available(self) -> bool:
        return sys.platform == "darwin" and shutil.which("say") is not None

    def speak(self, text: str, profile: Optional[VoiceProfile] = None) -> None:
        if not text.strip():
            return
        p = profile or VoiceProfile()
        cmd = ["say", "-r", str(p.rate)]
        voice = p.voice or self.voice
        if voice:
            cmd += ["-v", voice]
        self.stop()
        self._proc = subprocess.Popen(cmd + [text], stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
        self._proc.wait()
        self._proc = None

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None

    def voices(self) -> List[str]:
        try:
            out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True,
                                 timeout=5).stdout
            return [ln.split()[0] for ln in out.splitlines() if ln.strip()][:40]
        except Exception:
            return []


class PiperTTS(Synthesizer):
    """Piper — local neural TTS. Preferred when installed (better than `say`).

        brew install piper-tts   # or download a release
        # place a voice at ~/.origami/voices/<model>.onnx
    """

    name = "piper"

    def __init__(self, model: Optional[str] = None) -> None:
        self.binary = shutil.which("piper")
        self.model = model or os.getenv("ORIGAMI_PIPER_MODEL", "")
        if not self.model:
            voices = list((_voice_dir()).glob("*.onnx")) if _voice_dir().exists() else []
            self.model = str(voices[0]) if voices else ""
        self._proc: Optional[subprocess.Popen] = None

    def is_available(self) -> bool:
        return bool(self.binary and self.model and os.path.exists(self.model))

    def speak(self, text: str, profile: Optional[VoiceProfile] = None) -> None:
        if not text.strip() or not self.is_available():
            return
        self.stop()
        # piper streams raw audio; play it through the system player
        piper = subprocess.Popen([self.binary, "-m", self.model, "--output-raw"],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL)
        player = subprocess.Popen(["afplay", "-"] if sys.platform == "darwin"
                                  else ["aplay", "-r", "22050", "-f", "S16_LE", "-"],
                                  stdin=piper.stdout, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        self._proc = player
        piper.stdin.write(text.encode())
        piper.stdin.close()
        player.wait()
        self._proc = None

    def stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None


def _voice_dir():
    from pathlib import Path
    return Path.home() / ".origami" / "voices"


class SynthesizerManager(Synthesizer):
    """Picks the best available synthesizer; speaking runs off-thread so the
    caller can interrupt it."""

    name = "tts"

    def __init__(self, providers: Optional[List[Synthesizer]] = None,
                 profile: Optional[VoiceProfile] = None) -> None:
        self.providers = providers or [PiperTTS(), MacSayTTS()]
        self.profile = profile or VoiceProfile()
        self._thread: Optional[threading.Thread] = None
        self._active: Optional[Synthesizer] = None

    def active(self) -> Optional[Synthesizer]:
        for p in self.providers:
            if p.is_available():
                return p
        return None

    def is_available(self) -> bool:
        return self.active() is not None

    def speak(self, text: str, profile: Optional[VoiceProfile] = None) -> None:
        provider = self.active()
        if provider is None:
            return
        self._active = provider
        provider.speak(text, profile or self.profile)
        self._active = None

    def speak_async(self, text: str, profile: Optional[VoiceProfile] = None) -> None:
        self.stop()
        self._thread = threading.Thread(target=self.speak, args=(text, profile), daemon=True)
        self._thread.start()

    def is_speaking(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def stop(self) -> None:
        if self._active:
            self._active.stop()
        for p in self.providers:
            p.stop()

    def status(self) -> dict:
        provider = self.active()
        return {"provider": provider.name if provider else None,
                "available": provider is not None,
                "voice": self.profile.voice or getattr(provider, "voice", ""),
                "speaking": self.is_speaking()}
