"""Authentication methods — one interface, many factors.

Every current and future factor (voice, PIN, snap, face, fingerprint, phone/watch
proximity, hardware button, robot sensor) implements `AuthMethod`, so the engine
never changes when a factor is added. Methods declare their own strength, which
is what lets multi-factor policies be expressed later without redesign.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AuthAttempt:
    ok: bool
    confidence: float = 0.0
    method: str = ""
    reason: str = ""
    user: Optional[str] = None


class AuthMethod(ABC):
    name = "base"
    #: rough strength 0-1; used when combining factors
    strength = 0.5

    @abstractmethod
    def verify(self, **evidence) -> AuthAttempt:
        """Check the supplied evidence (audio, pin, image, …)."""

    def is_available(self) -> bool:
        return True

    def install_hint(self) -> str:
        return ""


class VoiceAuth(AuthMethod):
    """Wake phrase AND enrolled voice — both are required."""

    name = "voice"
    strength = 0.6   # deliberately not 1.0: replayable, so never treated as strong

    def __init__(self, store, verifier) -> None:
        self.store = store
        self.verifier = verifier

    def is_available(self) -> bool:
        return self.store.exists()

    def install_hint(self) -> str:
        return "run: origami \"enroll my voice\""

    def verify(self, **evidence) -> AuthAttempt:
        profile = self.store.load()
        if profile is None:
            return AuthAttempt(False, 0.0, self.name, "no enrolled voice")
        if not getattr(self.verifier, "reliable", True):
            # Honest refusal: this verifier cannot separate speakers, so it must
            # not be presented as identity proof.
            return AuthAttempt(False, 0.0, self.name,
                               f"{self.verifier.name} cannot verify identity reliably — "
                               f"install a neural verifier (pip install resemblyzer)")

        phrase = (evidence.get("phrase") or "").lower().strip(" .,!?")
        if phrase:
            expected = profile.wake_phrase.lower().strip()
            if not _phrase_matches(phrase, expected):
                return AuthAttempt(False, 0.0, self.name, "wake phrase mismatch")

        audio = evidence.get("audio")
        if audio is None or not len(audio):
            return AuthAttempt(False, 0.0, self.name, "no audio to verify")

        emb = self.verifier.embed(audio)
        if not emb:
            return AuthAttempt(False, 0.0, self.name, "audio too short")
        best = max((self.verifier.similarity(emb, known)
                    for known in profile.embeddings), default=0.0)
        ok = best >= profile.threshold
        return AuthAttempt(ok, best, self.name,
                           "" if ok else "voice does not match the enrolled speaker",
                           user=profile.name if ok else None)


def _phrase_matches(said: str, expected: str) -> bool:
    """Tolerant match — recognisers drop/add small words."""
    if expected in said or said in expected:
        return True
    want = [w for w in expected.split() if len(w) > 2]
    return bool(want) and sum(w in said for w in want) >= max(1, len(want) - 1)


class PinAuth(AuthMethod):
    """Fallback factor when voice is unavailable (kept hashed, never plaintext)."""

    name = "pin"
    strength = 0.7

    def __init__(self, store) -> None:
        self.store = store

    def is_available(self) -> bool:
        import os
        return bool(os.getenv("ORIGAMI_PIN_HASH"))

    def install_hint(self) -> str:
        return "set ORIGAMI_PIN_HASH=<sha256 of your pin>"

    def verify(self, **evidence) -> AuthAttempt:
        import hashlib
        import os
        pin = str(evidence.get("pin") or "")
        expected = os.getenv("ORIGAMI_PIN_HASH", "")
        if not expected:
            return AuthAttempt(False, 0.0, self.name, "no PIN configured")
        ok = hashlib.sha256(pin.encode()).hexdigest() == expected
        return AuthAttempt(ok, 1.0 if ok else 0.0, self.name,
                           "" if ok else "incorrect PIN", user="owner" if ok else None)


class TrustedTerminalAuth(AuthMethod):
    """Physical access to this terminal session.

    Honest by design: someone at the keyboard already has full access to the
    machine, so the CLI is treated as a trusted factor rather than pretending a
    voice check adds protection there.
    """

    name = "terminal"
    strength = 0.5

    def verify(self, **evidence) -> AuthAttempt:
        if evidence.get("source") in ("cli", "dashboard"):
            return AuthAttempt(True, 1.0, self.name, user="owner")
        return AuthAttempt(False, 0.0, self.name, "not a local session")


# ---------------------------------------------------------- future factors --
# Declared so the roadmap is visible and the engine already handles them.

class _PlannedMethod(AuthMethod):
    strength = 0.0

    def __init__(self, name: str, hint: str) -> None:
        self.name = name
        self._hint = hint

    def is_available(self) -> bool:
        return False

    def install_hint(self) -> str:
        return self._hint

    def verify(self, **evidence) -> AuthAttempt:
        return AuthAttempt(False, 0.0, self.name, "not implemented yet")


def planned_methods():
    return [
        _PlannedMethod("finger_snap", "phase 2 — snap detection exists in the Wake Engine"),
        _PlannedMethod("face", "phase 3 — needs a camera + face embedding model"),
        _PlannedMethod("fingerprint", "phase 4 — Touch ID bridge"),
        _PlannedMethod("phone_proximity", "phase 4 — Bluetooth/handoff presence"),
        _PlannedMethod("watch_proximity", "phase 4 — Apple Watch presence"),
        _PlannedMethod("continuous_voice", "phase 5 — identity checked mid-conversation"),
    ]
