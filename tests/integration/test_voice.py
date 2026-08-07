"""Voice Engine — routing, interruptions, context, speakable text. No audio I/O."""

from __future__ import annotations

from core.schemas.goal import Goal
from engines.voice.conversation import ConversationManager
from engines.voice.engine import VoiceEngine
from engines.voice.stt import Transcript
from engines.voice.wake import Trigger, WakeEngine
from main import build_orchestrator


class FakeTTS:
    def __init__(self):
        self.said, self.stopped = [], 0

    def is_available(self): return True
    def speak(self, text, profile=None): self.said.append(text)
    def speak_async(self, text, profile=None): self.said.append(text)
    def is_speaking(self): return False
    def stop(self): self.stopped += 1
    def status(self): return {"provider": "fake", "available": True, "voice": "x", "speaking": False}


class FakeSTT:
    def __init__(self, lines=()): self.lines = list(lines)
    def is_available(self): return True
    def listen(self, max_seconds=12.0):
        return Transcript(text=self.lines.pop(0)) if self.lines else Transcript(text="")
    def status(self): return {"provider": "fake", "model": "tiny", "mic": True,
                              "available": True, "install": ""}


def _engine(**kw):
    return VoiceEngine(orchestrator=build_orchestrator(), stt=FakeSTT(kw.pop("lines", [])),
                       tts=FakeTTS(), **kw)


# ------------------------------------------------------------- speakable text

def test_speakable_strips_markup_and_emoji():
    out = ConversationManager.speakable("✓ reminder.list → 🔥 Streak: 2\n- sleep\n- gym")
    assert "🔥" not in out and "→" not in out and "✓" not in out
    assert "Streak: 2" in out and "sleep" in out


def test_speakable_truncates_long_output():
    out = ConversationManager.speakable("word. " * 300)
    assert len(out) < 500 and "more on screen" in out


# ------------------------------------------------------------- interruptions

def test_interruption_words_detected():
    c = ConversationManager()
    assert c.interruption("stop") == "stop"
    assert c.interruption("wait a second") == "wait"
    assert c.interruption("never mind") == "cancel"
    assert c.interruption("continue") == "continue"
    assert c.interruption("play some lofi") is None


async def test_stop_interrupts_speech_without_running_a_tool():
    e = _engine()
    ex = await e.handle("stop")
    assert ex.control == "stop" and e.tts.stopped >= 1 and ex.tool is None


async def test_ending_phrases():
    assert ConversationManager.is_ending("goodbye")
    assert not ConversationManager.is_ending("what's next")


# ------------------------------------------------------------------- context

def test_context_resolves_pronouns():
    c = ConversationManager()
    c.note_context("scan careerlens", "code.scan")
    assert c.context["project"] == "careerlens"
    assert "careerlens" in c.resolve("explain it")


def test_history_records_both_sides():
    c = ConversationManager()
    c.add_user("hello"); c.add_origami("hi", tool="assistant.ask")
    h = c.history()
    assert [t["role"] for t in h] == ["user", "origami"]
    assert c.context["capability"] == "assistant"


# ------------------------------------------------- routes through orchestrator

async def test_voice_uses_the_normal_planner_no_duplicate_intent():
    e = _engine()
    ex = await e.handle("my reminders")
    assert ex.tool == "reminder.list"        # same routing as CLI
    assert ex.deterministic                   # Level 0 — no model needed
    assert e.tts.said                         # and it spoke the result


async def test_every_capability_is_voice_reachable():
    """Voice is a transport layer: whatever is registered is reachable."""
    e = _engine()
    for phrase, tool in {"play some lofi": "spotify.search_and_play",
                         "my goals": "goal.status",
                         "health check": "health.check",
                         "my codebases": "code.list"}.items():
        ex = await e.handle(phrase)
        assert ex.tool == tool, f"{phrase!r} -> {ex.tool}"


async def test_conversation_loop_until_goodbye():
    e = _engine(lines=["my reminders", "goodbye"])
    log = await e.converse(greet=False)
    assert len(log) == 1 and log[0].tool == "reminder.list"


# ---------------------------------------------------------------- wake engine

def test_wake_reports_triggers_and_manual_always_works():
    w = WakeEngine()
    kinds = {s["trigger"] for s in w.status()}
    assert {"wake_word", "finger_snap", "cli"} <= kinds
    assert w.trigger_now(Trigger.DASHBOARD).trigger is Trigger.DASHBOARD


def test_voice_status_reports_stack():
    e = _engine()
    s = e.status()
    assert s["can_speak"] and s["can_hear"] and "wake" in s


async def test_voice_skill_routing():
    orch = build_orchestrator()
    for text, tool in {"voice status": "voice.status", "stop talking": "voice.stop"}.items():
        plan = await orch.planner.plan(Goal(text=text))
        assert plan.steps[0].tool == tool, f"{text!r} -> {plan.steps[0].tool}"
