"""Authentication Engine — levels, sessions, gating, honest failure handling."""

from __future__ import annotations

import time

from core.schemas.goal import Goal
from engines.auth.engine import AuthenticationEngine, Level, level_for
from engines.auth.methods import AuthAttempt, AuthMethod, _phrase_matches
from engines.auth.profile import AttemptLog, IdentityStore, VoiceProfile
from engines.auth.session import Session
from engines.auth.verifier import SpectralVerifier
from main import build_orchestrator


class FakeVerifier(SpectralVerifier):
    """A *reliable* stand-in so gating logic can be tested deterministically."""
    name = "fake"
    reliable = True
    default_threshold = 0.8

    def embed(self, audio):
        return list(audio) if isinstance(audio, (list, tuple)) else [1.0, 0.0]


def _engine(tmp_path, verifier=None):
    return AuthenticationEngine(store=IdentityStore(tmp_path / "id.json"),
                                verifier=verifier or FakeVerifier(),
                                log=AttemptLog(tmp_path / "log.json"))


# ------------------------------------------------------------- security levels

def test_levels_map_from_tool_and_risk():
    assert level_for("assistant.ask") is Level.GENERAL
    assert level_for("memory.recall") is Level.PERSONAL
    assert level_for("terminal.run", "confirm") is Level.SENSITIVE
    assert level_for("anything", "critical") is Level.SENSITIVE


# ------------------------------------------------------------------ enrolment

def test_enroll_stores_embedding_not_audio(tmp_path):
    e = _engine(tmp_path)
    r = e.enroll([[1.0, 0.0], [0.9, 0.1]])
    assert r["ok"] and r["samples"] == 2
    saved = e.store.load()
    assert saved.embeddings and "audio" not in saved.to_dict()
    assert saved.wake_phrase == "i am iron man"


def test_enroll_rejects_empty_samples(tmp_path):
    class Empty(FakeVerifier):
        def embed(self, audio): return []
    assert _engine(tmp_path, Empty()).enroll([[0.0]])["ok"] is False


# ------------------------------------------------------- wake + verification

def test_wake_needs_phrase_and_matching_voice(tmp_path):
    e = _engine(tmp_path)
    e.enroll([[1.0, 0.0]])
    assert e.wake(audio=[1.0, 0.0], phrase="I am Iron Man").ok          # both correct
    assert not e.wake(audio=[1.0, 0.0], phrase="hello there").ok        # wrong phrase
    assert not e.wake(audio=[0.0, 1.0], phrase="I am Iron Man").ok      # wrong voice


def test_unknown_voice_is_ignored_with_reason(tmp_path):
    e = _engine(tmp_path)
    e.enroll([[1.0, 0.0]])
    a = e.wake(audio=[0.0, 1.0], phrase="I am Iron Man")
    assert not a.ok and "does not match" in a.reason


def test_phrase_matching_tolerates_recogniser_noise():
    assert _phrase_matches("i am iron man", "i am iron man")
    assert _phrase_matches("i am iron man.", "i am iron man")
    assert _phrase_matches("um i am iron man", "i am iron man")
    assert not _phrase_matches("open the pod bay doors", "i am iron man")


# --------------------------------------------------- unreliable verifier guard

def test_unreliable_verifier_refuses_to_prove_identity(tmp_path):
    """The numpy verifier cannot separate speakers — it must not gate anything."""
    e = _engine(tmp_path, SpectralVerifier())      # reliable = False
    e.store.save(VoiceProfile(embeddings=[[1.0, 0.0]], threshold=0.9))
    a = e.wake(audio=[1.0, 0.0] * 9000, phrase="i am iron man")
    assert not a.ok and "cannot verify identity reliably" in a.reason


# -------------------------------------------------------------------- session

def test_session_opens_expires_and_locks():
    s = Session(timeout=0.05)
    s.open("owner", "voice", 0.9)
    assert s.active
    s.lock(); assert not s.active
    s.unlock("owner", "voice", 0.9); assert s.active
    time.sleep(0.06)
    assert s.expired and not s.active


def test_level1_rides_open_session_level3_needs_confirmation(tmp_path):
    e = _engine(tmp_path)
    e.enroll([[1.0, 0.0]])
    e.wake(audio=[1.0, 0.0], phrase="i am iron man")
    assert e.require(Level.GENERAL).ok
    assert e.require(Level.PERSONAL).ok
    assert not e.require(Level.SENSITIVE).ok                     # needs confirmation
    assert e.require(Level.SENSITIVE, confirmed=True).ok


def test_locked_session_blocks_personal_actions(tmp_path):
    e = _engine(tmp_path)
    e.enroll([[1.0, 0.0]])
    e.wake(audio=[1.0, 0.0], phrase="i am iron man")
    e.lock()
    assert not e.require(Level.PERSONAL, audio=[0.0, 1.0], phrase="i am iron man").ok


def test_general_level_open_when_nobody_enrolled(tmp_path):
    """ORIGAMI stays usable before enrolment — chat is not gated."""
    assert _engine(tmp_path).require(Level.GENERAL).ok


# ------------------------------------------------------------ failure handling

def test_repeated_failures_lock_out(tmp_path):
    e = _engine(tmp_path)
    e.enroll([[1.0, 0.0]])
    for _ in range(5):
        e.wake(audio=[0.0, 1.0], phrase="i am iron man")
    assert e.status()["locked_out"]
    assert e.wake(audio=[1.0, 0.0], phrase="i am iron man").method == "lockout"


def test_attempt_log_records_without_personal_data(tmp_path):
    log = AttemptLog(tmp_path / "log.json")
    log.record(False, "voice", 0.3, "voice does not match")
    entry = log.recent()[0]
    assert entry["ok"] is False and "confidence" in entry
    assert "audio" not in entry and "text" not in entry


# ------------------------------------------------------------------- surface

def test_terminal_is_a_trusted_local_factor(tmp_path):
    e = _engine(tmp_path)
    e.enroll([[1.0, 0.0]])
    assert e.authenticate(source="cli").ok      # keyboard access == physical access


async def test_auth_skill_routing():
    orch = build_orchestrator()
    for text, tool in {"auth status": "auth.status", "lock origami": "auth.lock",
                       "enroll my voice": "auth.enroll"}.items():
        plan = await orch.planner.plan(Goal(text=text))
        assert plan.steps[0].tool == tool, f"{text!r} -> {plan.steps[0].tool}"
