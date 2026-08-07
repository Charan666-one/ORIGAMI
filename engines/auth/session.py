"""Authenticated session — stays open after a successful verification, expires
on inactivity, and can be locked or unlocked manually.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

DEFAULT_TIMEOUT = 15 * 60  # seconds of inactivity before re-verification


@dataclass
class Session:
    user: Optional[str] = None
    method: str = ""
    confidence: float = 0.0
    started_at: float = 0.0
    last_active: float = 0.0
    locked: bool = False
    timeout: float = DEFAULT_TIMEOUT

    # ------------------------------------------------------------- lifecycle

    def open(self, user: str, method: str, confidence: float) -> None:
        now = time.time()
        self.user, self.method, self.confidence = user, method, confidence
        self.started_at = self.last_active = now
        self.locked = False

    def touch(self) -> None:
        if self.active:
            self.last_active = time.time()

    def lock(self) -> None:
        self.locked = True

    def unlock(self, user: str, method: str, confidence: float) -> None:
        self.open(user, method, confidence)

    def close(self) -> None:
        self.user, self.method, self.confidence = None, "", 0.0
        self.started_at = self.last_active = 0.0
        self.locked = False

    # ----------------------------------------------------------------- state

    @property
    def expired(self) -> bool:
        return bool(self.user) and (time.time() - self.last_active) > self.timeout

    @property
    def active(self) -> bool:
        return bool(self.user) and not self.locked and not self.expired

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_active if self.last_active else 0.0

    def status(self) -> dict:
        return {"active": self.active, "user": self.user, "method": self.method,
                "confidence": round(self.confidence, 3), "locked": self.locked,
                "expired": self.expired, "idle_seconds": round(self.idle_seconds),
                "timeout": self.timeout}
