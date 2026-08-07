"""AuthSkill — enrol your voice, lock/unlock ORIGAMI, inspect identity status.

Enrolment records a few spoken samples, derives embeddings and discards the audio.
Everything stays on this machine.
"""

from __future__ import annotations

from typing import Any, List, Optional

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill

ENROL_PROMPTS = [
    "Say your wake phrase: I am Iron Man",
    "Again, naturally: I am Iron Man",
    "Once more, a little slower: I am Iron Man",
]


class AuthSkill(Skill):
    def __init__(self, engine: Any = None, recognizer: Any = None,
                 speak=None) -> None:
        self._engine = engine
        self._recognizer = recognizer
        self._speak = speak

    @property
    def engine(self):
        if self._engine is None:
            from engines.auth.engine import AuthenticationEngine
            self._engine = AuthenticationEngine()
        return self._engine

    @property
    def recognizer(self):
        if self._recognizer is None:
            from engines.voice.stt import RecognizerManager
            self._recognizer = RecognizerManager()
        return self._recognizer

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(name="auth.enroll",
                     description="Record your voice so ORIGAMI recognises you.",
                     risk=Risk.CONFIRM,
                     keywords=("enroll my voice", "enrol my voice", "register my voice",
                               "learn my voice", "train my voice", "set up voice id")),
            ToolSpec(name="auth.forget",
                     description="Delete the enrolled voice profile.",
                     risk=Risk.CRITICAL,
                     keywords=("forget my voice", "delete my voice", "remove voice id")),
            ToolSpec(name="auth.lock", description="Lock ORIGAMI (require re-verification).",
                     risk=Risk.SAFE,
                     keywords=("lock origami", "lock yourself", "lock the session", "lock down")),
            ToolSpec(name="auth.unlock", description="Unlock the session.",
                     risk=Risk.SAFE, keywords=("unlock origami", "unlock the session", "unlock")),
            ToolSpec(name="auth.status",
                     description="Who ORIGAMI thinks you are + authentication methods.",
                     risk=Risk.SAFE,
                     keywords=("auth status", "who am i", "identity status",
                               "am i authenticated", "security status")),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        if tool == "auth.enroll":
            return self._enroll()
        if tool == "auth.forget":
            self.engine.forget()
            return "🗑️  Voice profile deleted. ORIGAMI no longer recognises a voice."
        if tool == "auth.lock":
            self.engine.lock()
            return "🔒 Locked. Say your wake phrase to unlock."
        if tool == "auth.unlock":
            attempt = self.engine.unlock(source="cli")
            return ("🔓 Unlocked." if attempt.ok
                    else f"Couldn't unlock: {attempt.reason}")
        if tool == "auth.status":
            return self._status()
        raise ValueError(f"Unknown tool: {tool}")

    # ------------------------------------------------------------------ enrol

    def _enroll(self) -> str:
        if not self.recognizer.is_available():
            return ("I need a microphone to learn your voice.\n"
                    f"   → {self.recognizer.install_hint()}")
        samples = []
        say = self._speak or (lambda t: None)
        for prompt in ENROL_PROMPTS:
            print(f"🎙️  {prompt}")
            say(prompt)
            audio = self.recognizer.mic.record(max_seconds=6.0, silence_seconds=1.2)
            if audio is not None and len(audio):
                samples.append(audio)
        if not samples:
            return "I didn't hear anything — enrolment cancelled."

        result = self.engine.enroll(samples)
        if not result.get("ok"):
            return f"Enrolment failed: {result.get('error')}"
        return (f"✅ Voice enrolled — {result['samples']} samples "
                f"({result['verifier']}, consistency {result['consistency']}).\n"
                f"   Wake phrase: “{result['wake_phrase']}”\n"
                f"   Raw audio was discarded; only the embedding is stored.\n"
                f"   ⚠️  Voice ID is a convenience gate, not strong security — it can be "
                f"fooled by a recording.")

    # ----------------------------------------------------------------- status

    def _status(self) -> str:
        s = self.engine.status()
        sess = s["session"]
        lines = ["🔐 AUTHENTICATION ENGINE"]
        if s["enrolled"]:
            lines.append(f"   Enrolled : ✅ {s['user']} · {s['samples']} samples · "
                         f"{s['verifier']} (threshold {s['threshold']})")
            lines.append(f"   Wake     : “{s['wake_phrase']}” (voice must match too)")
        else:
            lines.append("   Enrolled : ○ nobody — run: origami \"enroll my voice\"")
        lines.append(f"   Session  : {'🔓 active as ' + str(sess['user']) if sess['active'] else '🔒 locked' if sess['locked'] else '○ none'}"
                     + (f" · idle {sess['idle_seconds']}s" if sess["active"] else ""))
        lines.append("   Methods  :")
        for m in s["methods"]:
            mark = "✅" if m["available"] else "○"
            hint = f" — {m['install']}" if not m["available"] and m["install"] else ""
            lines.append(f"     {mark} {m['name']} (strength {m['strength']}){hint}")
        lines.append("   Planned  : " + ", ".join(p["name"] for p in s["planned"]))
        if s["recent_failures"]:
            lines.append(f"   ⚠️  {s['recent_failures']} recent failed attempt(s)"
                         + (" — LOCKED OUT" if s["locked_out"] else ""))
        lines.append("   Levels: 1 chat · 2 personal (verified) · 3 sensitive (verified + confirm)")
        return "\n".join(lines)
