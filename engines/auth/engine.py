"""AuthenticationEngine — the single gateway for identity in ORIGAMI.

    passive listening → wake detection → speaker verification → session → execution

Security levels map onto ORIGAMI's existing risk tiers rather than duplicating
them, so one policy governs both typed and spoken commands:

    Level 1  general conversation      — open session is enough        (Risk.SAFE)
    Level 2  personal information      — verified speaker required     (Risk.CONFIRM)
    Level 3  sensitive operations      — verified speaker + explicit confirm (Risk.CRITICAL)

Everything is local: enrolment produces embeddings, raw audio is discarded, and
nothing is uploaded.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any, Dict, List, Optional

from engines.auth.methods import (AuthAttempt, AuthMethod, PinAuth, TrustedTerminalAuth,
                                  VoiceAuth, planned_methods)
from engines.auth.profile import AttemptLog, IdentityStore, VoiceProfile
from engines.auth.session import Session
from engines.auth.verifier import best_verifier

LOCKOUT_AFTER = 5          # failed attempts within the window
LOCKOUT_WINDOW = 300.0     # seconds


class Level(IntEnum):
    GENERAL = 1     # chat, questions
    PERSONAL = 2    # memory, projects, calendar, email drafts
    SENSITIVE = 3   # terminal, deletion, money, robot movement


#: capability family -> minimum level required
FAMILY_LEVEL = {
    "terminal": Level.SENSITIVE, "email": Level.SENSITIVE, "github": Level.SENSITIVE,
    "memory": Level.PERSONAL, "profile": Level.PERSONAL, "calendar": Level.PERSONAL,
    "goal": Level.PERSONAL, "reminder": Level.PERSONAL, "projects": Level.PERSONAL,
    "code": Level.PERSONAL, "brief": Level.PERSONAL,
}


def level_for(tool: Optional[str], risk: str = "safe") -> Level:
    """Required level for a tool — risk tier wins, family is the floor."""
    if risk == "critical":
        return Level.SENSITIVE
    family = (tool or "").split(".", 1)[0]
    base = FAMILY_LEVEL.get(family, Level.GENERAL)
    if risk == "confirm":
        return max(base, Level.SENSITIVE)
    return base


class AuthenticationEngine:
    def __init__(self, store: Optional[IdentityStore] = None, verifier=None,
                 session: Optional[Session] = None, log: Optional[AttemptLog] = None,
                 methods: Optional[List[AuthMethod]] = None) -> None:
        self.store = store or IdentityStore()
        self.verifier = verifier or best_verifier()
        self.session = session or Session()
        self.log = log or AttemptLog()
        self.methods: List[AuthMethod] = methods or [
            VoiceAuth(self.store, self.verifier), PinAuth(self.store),
            TrustedTerminalAuth()]

    # ------------------------------------------------------------- enrolment

    def enroll(self, samples: List[Any], name: str = "owner",
               wake_phrase: Optional[str] = None,
               threshold: Optional[float] = None) -> Dict[str, Any]:
        """Turn a few spoken samples into a stored voice profile (audio discarded)."""
        embeddings = [e for e in (self.verifier.embed(s) for s in samples) if e]
        if not embeddings:
            return {"ok": False, "error": "Samples were too short or silent."}

        profile = self.store.load() or VoiceProfile()
        profile.name = name
        profile.embeddings = embeddings
        profile.verifier = self.verifier.name
        profile.threshold = threshold or self.verifier.default_threshold
        profile.samples = len(embeddings)
        if wake_phrase:
            profile.wake_phrase = wake_phrase.lower().strip()
        self.store.save(profile)

        # consistency of the enrolment itself — a useful sanity signal
        sims = [self.verifier.similarity(a, b)
                for i, a in enumerate(embeddings) for b in embeddings[i + 1:]]
        return {"ok": True, "samples": len(embeddings), "verifier": self.verifier.name,
                "threshold": profile.threshold, "wake_phrase": profile.wake_phrase,
                "consistency": round(sum(sims) / len(sims), 3) if sims else 1.0}

    def is_enrolled(self) -> bool:
        return self.store.exists()

    def forget(self) -> None:
        self.store.clear()
        self.session.close()

    # -------------------------------------------------------- authentication

    def authenticate(self, **evidence) -> AuthAttempt:
        """Try every available method; the first success opens the session."""
        if self.log.recent_failures(LOCKOUT_WINDOW) >= LOCKOUT_AFTER:
            return AuthAttempt(False, 0.0, "lockout",
                               "too many failed attempts — try again later")

        best = AuthAttempt(False, 0.0, "none", "no authentication method available")
        for method in self.methods:
            if not method.is_available():
                continue
            attempt = method.verify(**evidence)
            if attempt.ok:
                self.session.open(attempt.user or "owner", attempt.method, attempt.confidence)
                self.log.record(True, attempt.method, attempt.confidence)
                return attempt
            # strictly greater: on ties the earlier (higher-priority) method's
            # reason wins, so the user sees "voice didn't match", not a fallback's
            if attempt.confidence > best.confidence or best.method == "none":
                best = attempt
        self.log.record(False, best.method, best.confidence, best.reason)
        return best

    def wake(self, audio=None, phrase: str = "") -> AuthAttempt:
        """Wake attempt: the phrase alone never activates ORIGAMI — the voice must
        match too. An unknown voice is silently ignored."""
        return self.authenticate(audio=audio, phrase=phrase, source="voice")

    # ------------------------------------------------------------ authorising

    def require(self, level: Level, source: str = "voice", **evidence) -> AuthAttempt:
        """Gate an action. Level 1 rides an open session; 2+ needs verification."""
        if self.session.active:
            self.session.touch()
            if level <= Level.PERSONAL:
                return AuthAttempt(True, self.session.confidence, self.session.method,
                                   user=self.session.user)
            # Level 3 additionally needs an explicit confirmation from the caller
            if evidence.get("confirmed"):
                return AuthAttempt(True, self.session.confidence, self.session.method,
                                   user=self.session.user)
            return AuthAttempt(False, self.session.confidence, self.session.method,
                               "sensitive action needs explicit confirmation")

        if level == Level.GENERAL and not self.is_enrolled():
            return AuthAttempt(True, 1.0, "open", "no identity enrolled")
        return self.authenticate(source=source, **evidence)

    def authorize_tool(self, tool: str, risk: str = "safe", source: str = "voice",
                       **evidence) -> AuthAttempt:
        return self.require(level_for(tool, risk), source=source, **evidence)

    # ----------------------------------------------------------------- locks

    def lock(self) -> None:
        self.session.lock()

    def unlock(self, **evidence) -> AuthAttempt:
        self.session.locked = False
        return self.authenticate(**evidence)

    # ---------------------------------------------------------------- status

    def status(self) -> Dict[str, Any]:
        profile = self.store.load()
        return {
            "enrolled": profile is not None,
            "user": profile.name if profile else None,
            "wake_phrase": profile.wake_phrase if profile else None,
            "threshold": profile.threshold if profile else None,
            "verifier": self.verifier.name,
            "samples": profile.samples if profile else 0,
            "session": self.session.status(),
            "methods": [{"name": m.name, "available": m.is_available(),
                         "strength": m.strength, "install": m.install_hint()}
                        for m in self.methods],
            "planned": [{"name": m.name, "install": m.install_hint()}
                        for m in planned_methods()],
            "recent_failures": self.log.recent_failures(LOCKOUT_WINDOW),
            "locked_out": self.log.recent_failures(LOCKOUT_WINDOW) >= LOCKOUT_AFTER,
        }
