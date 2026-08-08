"""Wake authentication — configurable phrase, speaker verification, sessions.

Covers every case the spec listed. Keyless: fake verifier + fake audio, no mic.
"""

from __future__ import annotations

import time

from core.schemas.goal import Goal
from engines.auth.engine import AuthenticationEngine
from engines.auth.listener import ListenState, PassiveListener
from engines.auth.profile import AttemptLog, IdentityStore
from engines.auth.settings import WakeSettings, WakeSettingsStore
from engines.auth.verifier import SpectralVerifier
from engines.voice.stt import Transcript
from main import build_orchestrator

ME = [1.0, 0.0]            # "my" voice embedding
IMPOSTER = [0.0, 1.0]      # someone else


class FakeVerifier(SpectralVerifier):
    name = "fake"
    reliable = True
    default_threshold = 0.8

    def embed(self, audio):
        return list(audio) if isinstance(audio, (list, tuple)) else [1.0, 0.0]


class FakeSTT:
    """Feeds scripted (audio, transcript) pairs instead of a microphone."""

    def __init__(self, script=()):
        self.script = list(script)
        self.mic = self

    def is_available(self): return True

    def record(self, max_seconds=4.0, silence_seconds=1.0):
        return self.script[0][0] if self.script else None

    def transcribe(self, audio):
        return Transcript(text=self.script.pop(0)[1] if self.script else "")

    def listen(self, max_seconds=10.0):
        return self.transcribe(None)


def _setup(tmp_path, phrase="i am iron man", **cfg):
    settings = WakeSettingsStore(tmp_path / "wake.json")
    settings.save(WakeSettings(wake_phrase=phrase, **cfg))
    auth = AuthenticationEngine(store=IdentityStore(tmp_path / "id.json"),
                                verifier=FakeVerifier(),
                                log=AttemptLog(tmp_path / "log.json"),
                                settings=settings)
    auth.enroll([ME])
    return auth, settings


def _listener(tmp_path, script, **cfg):
    auth, settings = _setup(tmp_path, **cfg)
    return PassiveListener(auth=auth, recognizer=FakeSTT(script),
                           settings_store=settings), auth


# ------------------------------------------------- the four core combinations

def test_right_phrase_right_speaker_activates(tmp_path):
    listener, auth = _listener(tmp_path, [])
    attempt = listener.try_wake(ME, "I am Iron Man")
    assert attempt.phrase_matched and attempt.speaker_ok and attempt.activated
    assert auth.session.active
    assert listener.state is ListenState.AUTHENTICATED


def test_right_phrase_wrong_speaker_is_ignored(tmp_path):
    listener, auth = _listener(tmp_path, [])
    attempt = listener.try_wake(IMPOSTER, "I am Iron Man")
    assert attempt.phrase_matched and not attempt.speaker_ok
    assert not attempt.activated and not auth.session.active
    assert listener.state is ListenState.UNKNOWN_SPEAKER


def test_wrong_phrase_right_speaker_does_nothing(tmp_path):
    listener, auth = _listener(tmp_path, [])
    attempt = listener.try_wake(ME, "what's the weather")
    assert not attempt.phrase_matched and not attempt.activated
    assert not auth.session.active


def test_background_audio_never_activates(tmp_path):
    """TV / YouTube / other people talking."""
    listener, auth = _listener(tmp_path, [])
    for noise in ("and then he said I am Iron Man", "buy now for only 9.99", ""):
        listener.try_wake(IMPOSTER, noise)
    assert not auth.session.active


def test_recorded_voice_of_someone_else_is_rejected(tmp_path):
    listener, auth = _listener(tmp_path, [])
    assert not listener.try_wake(IMPOSTER, "i am iron man").activated


# ------------------------------------------------------ configurable phrase

def test_wake_phrase_is_configurable(tmp_path):
    listener, auth = _listener(tmp_path, [], phrase="hey origami")
    assert not listener.try_wake(ME, "I am Iron Man").phrase_matched
    assert listener.try_wake(ME, "hey origami").activated


def test_changing_the_phrase_needs_no_code_change(tmp_path):
    listener, auth = _listener(tmp_path, [])
    assert listener.try_wake(ME, "i am iron man").activated
    auth.session.close()
    listener.settings_store.update(wake_phrase="computer")
    assert listener.try_wake(ME, "computer").activated
    auth.session.close()
    assert not listener.try_wake(ME, "i am iron man").phrase_matched


def test_phrase_alone_can_be_allowed_but_is_off_by_default(tmp_path):
    strict, _ = _listener(tmp_path / "a", [])
    assert strict.settings_store.load().require_voice_match
    relaxed, _ = _listener(tmp_path / "b", [], require_voice_match=False)
    assert relaxed.try_wake(IMPOSTER, "i am iron man").activated  # opt-in only


# ------------------------------------------------------------------ sessions

def test_session_allows_natural_follow_ups(tmp_path):
    listener, auth = _listener(tmp_path, [])
    listener.try_wake(ME, "i am iron man")
    # no wake phrase needed for subsequent requests
    from engines.auth.engine import Level
    assert auth.require(Level.PERSONAL).ok
    assert auth.require(Level.GENERAL).ok


def test_session_times_out(tmp_path):
    listener, auth = _listener(tmp_path, [], session_timeout=0.05)
    listener.try_wake(ME, "i am iron man")
    assert auth.session.active
    time.sleep(0.06)
    assert not auth.session.active


def test_manual_lock(tmp_path):
    listener, auth = _listener(tmp_path, [])
    listener.try_wake(ME, "i am iron man")
    auth.lock()
    assert not auth.session.active
    assert PassiveListener._is_lock_command("origami lock")
    assert not PassiveListener._is_lock_command("open safari")


def test_disabled_listening_never_activates(tmp_path):
    listener, auth = _listener(tmp_path, [], enabled=False)
    assert not listener.try_wake(ME, "i am iron man").activated
    assert listener.state is ListenState.DISABLED


# --------------------------------------------------- permissions still apply

def test_authentication_does_not_bypass_permissions(tmp_path):
    """Level 3 still needs explicit confirmation even when authenticated."""
    from engines.auth.engine import Level
    listener, auth = _listener(tmp_path, [])
    listener.try_wake(ME, "i am iron man")
    assert not auth.require(Level.SENSITIVE).ok
    assert auth.require(Level.SENSITIVE, confirmed=True).ok


def test_repeated_failures_keep_it_locked(tmp_path):
    listener, auth = _listener(tmp_path, [])
    for _ in range(6):
        listener.try_wake(IMPOSTER, "i am iron man")
    assert not auth.session.active and auth.status()["locked_out"]


# ------------------------------------------------------------- re-enrolment

def test_re_enrollment_replaces_the_profile(tmp_path):
    auth, _ = _setup(tmp_path)
    first = auth.store.load().embeddings
    auth.enroll([[0.5, 0.5], [0.5, 0.5]])
    assert auth.store.load().embeddings != first
    assert auth.store.load().samples == 2


def test_forget_removes_everything(tmp_path):
    auth, _ = _setup(tmp_path)
    auth.forget()
    assert not auth.is_enrolled() and not auth.session.active


# ------------------------------------------------------------------ surfaces

def test_listener_reports_dashboard_states(tmp_path):
    listener, _ = _listener(tmp_path, [])
    s = listener.status()
    assert s["wake_phrase"] == "i am iron man" and s["requires_voice"]
    assert s["state"] in {st.value for st in ListenState}


async def test_wake_phrase_tool_routing():
    orch = build_orchestrator()
    plan = await orch.planner.plan(Goal(text='change my wake phrase to hey origami'))
    assert plan.steps[0].tool == "auth.wake_phrase"
