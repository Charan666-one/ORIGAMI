"""PassiveListener — wake → verify → session, continuously.

    microphone → wake phrase? → is it MY voice? → session ACTIVE → converse

The whole point: never type anything to activate a personal assistant. A wake
phrase alone is not authentication — an unknown speaker saying it is ignored in
silence, which is also the defence against TV audio, videos and other people.

Once authenticated the session stays open, so follow-up sentences need no wake
phrase, until inactivity (configurable) or "lock" closes it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional


class ListenState(str, Enum):
    LOCKED = "LOCKED"
    LISTENING = "LISTENING"          # waiting for the wake phrase
    WAKE_DETECTED = "WAKE_DETECTED"  # phrase heard, identity unknown
    VERIFYING = "VERIFYING"          # comparing against the enrolled voice
    AUTHENTICATED = "AUTHENTICATED"  # it is the owner
    SESSION_ACTIVE = "SESSION_ACTIVE"
    SESSION_LOCKED = "SESSION_LOCKED"
    UNKNOWN_SPEAKER = "UNKNOWN_SPEAKER"
    DISABLED = "DISABLED"


@dataclass
class WakeAttempt:
    heard: str = ""
    phrase_matched: bool = False
    speaker_ok: bool = False
    confidence: float = 0.0
    activated: bool = False
    reason: str = ""


class PassiveListener:
    def __init__(self, auth, recognizer, settings_store, voice=None,
                 on_state: Optional[Callable[[str, str], None]] = None) -> None:
        self.auth = auth
        self.stt = recognizer
        self.settings_store = settings_store
        self.voice = voice                       # optional VoiceEngine, for replies
        self.on_state = on_state or (lambda s, d="": None)
        self.state = ListenState.LOCKED
        self.history: List[WakeAttempt] = []

    # ------------------------------------------------------------------ state

    def _set(self, state: ListenState, detail: str = "") -> None:
        self.state = state
        try:
            self.on_state(state.value, detail)
        except Exception:
            pass

    # ------------------------------------------------------------------- wake

    def try_wake(self, audio, transcript: str) -> WakeAttempt:
        """One activation attempt: phrase must match AND the voice must be mine."""
        settings = self.settings_store.load()
        attempt = WakeAttempt(heard=transcript)

        if not settings.enabled:
            attempt.reason = "passive listening disabled"
            self._set(ListenState.DISABLED)
            return attempt

        from engines.auth.methods import _phrase_matches
        attempt.phrase_matched = _phrase_matches(
            transcript.lower().strip(" .,!?"), settings.wake_phrase.lower())
        if not attempt.phrase_matched:
            attempt.reason = "no wake phrase"
            self._set(ListenState.LISTENING)
            return attempt

        self._set(ListenState.WAKE_DETECTED, transcript)
        if not settings.require_voice_match:
            attempt.speaker_ok = attempt.activated = True
            self._set(ListenState.AUTHENTICATED)
            return attempt

        self._set(ListenState.VERIFYING)
        result = self.auth.wake(audio=audio, phrase=transcript)
        attempt.confidence = result.confidence
        attempt.speaker_ok = attempt.activated = bool(result.ok)
        attempt.reason = result.reason
        self.history.append(attempt)

        if attempt.activated:
            self.auth.session.timeout = settings.session_timeout
            self._set(ListenState.AUTHENTICATED, f"{result.confidence:.2f}")
        else:
            # Deliberate silence: never tell an unknown speaker why they failed.
            self._set(ListenState.UNKNOWN_SPEAKER, result.reason)
        return attempt

    # ------------------------------------------------------------- the loop

    def run(self, max_cycles: Optional[int] = None, chunk_seconds: float = 4.0) -> None:
        """Listen forever (or `max_cycles` times, for tests)."""
        settings = self.settings_store.load()
        if not settings.enabled:
            self._set(ListenState.DISABLED)
            return
        self._set(ListenState.LISTENING)

        cycles = 0
        while max_cycles is None or cycles < max_cycles:
            cycles += 1

            if self.auth.session.active:
                self._set(ListenState.SESSION_ACTIVE)
                heard = self.stt.listen(max_seconds=10.0)
                if not heard.text:
                    if self.auth.session.expired:
                        self._set(ListenState.SESSION_LOCKED)
                    continue
                if self._is_lock_command(heard.text):
                    self.auth.lock()
                    self._say("Locked.")
                    self._set(ListenState.SESSION_LOCKED)
                    continue
                self.auth.session.touch()
                self._handle(heard.text)
                continue

            # locked: listen for the wake phrase
            self._set(ListenState.LISTENING)
            audio = self.stt.mic.record(max_seconds=chunk_seconds, silence_seconds=1.0)
            if audio is None or not len(audio):
                continue
            transcript = self.stt.transcribe(audio).text
            if not transcript.strip():
                continue

            attempt = self.try_wake(audio, transcript)
            if attempt.activated:
                self._say("Yes?")
                self._set(ListenState.SESSION_ACTIVE)

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _is_lock_command(text: str) -> bool:
        low = text.lower().strip(" .,!?")
        return low in ("lock", "origami lock", "lock origami", "lock yourself",
                       "go to sleep", "sleep now")

    def _say(self, text: str) -> None:
        if self.voice is not None:
            try:
                self.voice.say(text, wait=False)
            except Exception:
                pass

    def _handle(self, text: str) -> None:
        """Run an authenticated request through the normal orchestrator."""
        if self.voice is None:
            return
        import asyncio
        try:
            asyncio.run(self.voice.handle(text))
        except RuntimeError:                     # already inside a loop
            pass

    # ---------------------------------------------------------------- status

    def status(self) -> dict:
        settings = self.settings_store.load()
        recent = self.history[-5:]
        return {
            "state": self.state.value,
            "wake_phrase": settings.wake_phrase,
            "detector": settings.wake_detector,
            "threshold": settings.confidence_threshold,
            "enabled": settings.enabled,
            "requires_voice": settings.require_voice_match,
            "session": self.auth.session.status(),
            "recent_attempts": [
                {"heard": a.heard[:40], "phrase": a.phrase_matched,
                 "speaker": a.speaker_ok, "confidence": round(a.confidence, 2)}
                for a in recent
            ],
        }
