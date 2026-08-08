"""VoiceSkill — speak, listen, and report the voice stack's status.

Voice is a transport layer, so this skill is intentionally small: the conversation
loop lives in the Voice Engine and routes through the normal orchestrator.
"""

from __future__ import annotations

from typing import Any, List, Optional

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill


class VoiceSkill(Skill):
    def __init__(self, engine: Any = None) -> None:
        self._engine = engine

    @property
    def engine(self):
        if self._engine is None:
            from engines.voice.engine import VoiceEngine
            self._engine = VoiceEngine()
        return self._engine

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(name="voice.status",
                     description="Show the voice stack: hearing, speech, wake triggers.",
                     risk=Risk.SAFE,
                     keywords=("voice status", "can you hear", "can you talk",
                               "voice setup", "is voice ready")),
            ToolSpec(name="voice.say", description="Speak something out loud.",
                     params={"text": "what to say"}, risk=Risk.SAFE,
                     keywords=("say out loud", "say aloud", "speak ", "say ", "read that out",
                               "tell me out loud")),
            ToolSpec(name="voice.stop", description="Stop speaking immediately.",
                     risk=Risk.SAFE,
                     keywords=("stop talking", "be quiet", "stop speaking")),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        if tool == "voice.say":
            text = (kwargs.get("text") or "").strip()
            if not text:
                return "What should I say?"
            if not self.engine.tts.is_available():
                return "No speech synthesizer available."
            self.engine.say(text, wait=False)
            return f"🔊 “{text}”"
        if tool == "voice.stop":
            self.engine.stop_speaking()
            return "Stopped."
        if tool == "voice.status":
            return self._status()
        raise ValueError(f"Unknown tool: {tool}")

    def _status(self) -> str:
        s = self.engine.status()
        lines = [
            f"🎙️  VOICE ENGINE — {'ready' if s['ready'] else 'partial'}",
            f"   Hearing : {'✅ ' + (s['stt']['provider'] or '') + ' ' + (s['stt']['model'] or '') if s['can_hear'] else '⚠️  not installed'}",
            f"   Speaking: {'✅ ' + (s['tts']['provider'] or '') if s['can_speak'] else '⚠️  unavailable'}",
        ]
        if not s["can_hear"] and s["stt"].get("install"):
            lines.append(f"   → enable hearing: {s['stt']['install']}")
        lines.append("   Wake triggers:")
        for w in s["wake"]:
            mark = "✅" if w["available"] else "○"
            extra = f" — {w['install']}" if w["install"] else ""
            phrase = f" (“{w['phrase']}”)" if w.get("phrase") else ""
            lines.append(f"     {mark} {w['trigger']}{phrase}{extra}")
        lines.append("   Start a conversation:  origami voice")
        return "\n".join(lines)
