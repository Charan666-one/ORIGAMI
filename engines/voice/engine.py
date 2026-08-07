"""VoiceEngine — the universal interaction layer.

    mic → wake → speech recognition → [intent] → orchestrator → response → speech

Deliberately thin: it does NOT re-implement intent detection, planning or
capabilities. ORIGAMI's planner already routes deterministically (Level 0 needs no
model at all), so voice reuses it — which is exactly why no capability has to
implement voice separately. Every capability that exists, or ever will, is
reachable by voice the moment it is registered.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from core.schemas.goal import Goal
from engines.voice.conversation import ConversationManager
from engines.voice.stt import RecognizerManager, Transcript
from engines.voice.tts import SynthesizerManager, VoiceProfile
from engines.voice.wake import Trigger, WakeEngine


@dataclass
class VoiceExchange:
    heard: str
    said: str
    tool: Optional[str] = None
    control: Optional[str] = None      # stop | cancel | wait | continue
    deterministic: bool = False        # answered with no LLM
    latency: float = 0.0


class VoiceEngine:
    """States mirror the dashboard Core so the UI can animate the same lifecycle."""

    STATES = ("idle", "listening", "thinking", "executing", "speaking", "error")

    def __init__(self, orchestrator=None, stt=None, tts=None, wake=None,
                 conversation=None, on_state: Optional[Callable[[str, str], None]] = None,
                 profile: Optional[VoiceProfile] = None) -> None:
        self._orchestrator = orchestrator
        self.stt = stt or RecognizerManager()
        self.tts = tts or SynthesizerManager(profile=profile)
        self.wake = wake or WakeEngine()
        self.conv = conversation or ConversationManager()
        self.on_state = on_state or (lambda state, detail="": None)
        self.state = "idle"

    # ------------------------------------------------------------- plumbing

    def orchestrator(self):
        if self._orchestrator is None:
            from main import build_orchestrator
            self._orchestrator = build_orchestrator(confirmer=self._voice_confirm)
        return self._orchestrator

    async def _voice_confirm(self, spec, step) -> bool:
        """Consequential actions are never auto-approved by voice."""
        self.say(f"{spec.name.replace('.', ' ')} needs confirmation. "
                 f"Approve it from the terminal or dashboard.")
        return False

    def _set(self, state: str, detail: str = "") -> None:
        self.state = state
        try:
            self.on_state(state, detail)
        except Exception:
            pass

    # ---------------------------------------------------------------- speak

    def say(self, text: str, wait: bool = True) -> str:
        spoken = self.conv.speakable(text)
        if not spoken or not self.tts.is_available():
            return spoken
        self._set("speaking", spoken)
        self.conv.speaking = True
        if wait:
            self.tts.speak(spoken)
            self.conv.speaking = False
            self._set("idle")
        else:
            self.tts.speak_async(spoken)
        return spoken

    def stop_speaking(self) -> None:
        self.tts.stop()
        self.conv.speaking = False
        self._set("idle")

    # --------------------------------------------------------------- listen

    def listen(self, max_seconds: float = 12.0) -> Transcript:
        self._set("listening")
        t = self.stt.listen(max_seconds=max_seconds)
        self._set("idle")
        return t

    # ------------------------------------------------------- one exchange

    async def handle(self, text: str) -> VoiceExchange:
        """Text in → ORIGAMI acts → spoken reply out. The heart of the loop."""
        started = time.perf_counter()
        text = (text or "").strip()
        if not text:
            return VoiceExchange(heard="", said="")

        # 1. interruption / control words take priority over any request
        control = self.conv.interruption(text)
        if control:
            if control in ("stop", "cancel"):
                self.stop_speaking()
                said = "" if control == "stop" else self.say("Cancelled.")
                return VoiceExchange(text, said, control=control,
                                     latency=time.perf_counter() - started)
            if control == "wait":
                self.stop_speaking()
                return VoiceExchange(text, self.say("Waiting."), control=control,
                                     latency=time.perf_counter() - started)
            if control == "continue":
                return VoiceExchange(text, self.say("Go ahead."), control=control,
                                     latency=time.perf_counter() - started)

        # 2. resolve pronouns from conversation context ("explain it")
        resolved = self.conv.resolve(text)
        self.conv.add_user(text)

        # 3. route through ORIGAMI's own planner/registry (no duplicate intent logic)
        self._set("thinking", resolved)
        orch = self.orchestrator()
        plan = await orch.planner.plan(Goal(text=resolved, source="voice"))
        tool = plan.steps[0].tool if plan.steps else None
        deterministic = bool(tool) and not tool.startswith("assistant.")

        self._set("executing", tool or "")
        result = await orch.handle(Goal(text=resolved, source="voice"))

        # 4. speak the outcome
        self.conv.note_context(resolved, tool)
        said = self.say(result.summary)
        self.conv.add_origami(said, tool=tool)
        return VoiceExchange(heard=text, said=said, tool=tool,
                             deterministic=deterministic,
                             latency=time.perf_counter() - started)

    # ------------------------------------------------- continuous session

    async def converse(self, turns: int = 20, greet: bool = True) -> List[VoiceExchange]:
        """A full spoken session: listen → act → speak, until goodbye."""
        log: List[VoiceExchange] = []
        if not self.stt.is_available():
            self.say("I can speak, but I can't hear yet.")
            return log
        if greet:
            self.say("I'm listening.")
        for _ in range(turns):
            heard = self.listen()
            if not heard.text:
                continue
            if self.conv.is_ending(heard.text):
                self.say("Goodbye.")
                break
            log.append(await self.handle(heard.text))
        return log

    # --------------------------------------------------------------- status

    def status(self) -> Dict[str, Any]:
        stt = self.stt.status()
        tts = self.tts.status()
        return {
            "state": self.state,
            "can_hear": stt["available"],
            "can_speak": tts["available"],
            "stt": stt,
            "tts": tts,
            "wake": self.wake.status(),
            "context": self.conv.context,
            "history": self.conv.history(),
            "ready": stt["available"] and tts["available"],
        }
