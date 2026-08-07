"""Conversation Manager — context, history, interruptions, response shaping.

Keeps track of what is being talked about (task / project / capability) so the
user never has to repeat themselves, recognises interruption words while ORIGAMI
is speaking, and turns tool output into something that sounds natural when spoken.

Speaker identity and emotion are declared on `Turn` now, so speaker recognition
and emotion detection slot in later without changing this interface.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Said while ORIGAMI is speaking -> control, not a new request.
INTERRUPTS = {
    "stop": "stop", "shut up": "stop", "quiet": "stop", "cancel": "cancel",
    "never mind": "cancel", "nevermind": "cancel", "wait": "wait", "hold on": "wait",
    "pause": "wait", "continue": "continue", "go on": "continue", "carry on": "continue",
}
ENDINGS = {"goodbye", "bye", "that's all", "thats all", "exit", "quit", "stop listening"}

_EMOJI = re.compile(r"[\U0001F000-\U0001FAFF☀-➿️]")
_MARKUP = re.compile(r"[*_`#>]|https?://\S+")
# CLI output starts with the tool name ("✓ reminder.list → …") — noise when spoken
_TOOL_PREFIX = re.compile(r"^\s*[✓✗]?\s*[a-z_]+\.[a-z_]+\s*(?:→|->|,)?\s*", re.IGNORECASE)


@dataclass
class Turn:
    role: str                 # user | origami
    text: str
    tool: Optional[str] = None
    at: float = field(default_factory=time.time)
    speaker: str = "owner"    # reserved: speaker recognition / multi-user
    emotion: str = "neutral"  # reserved: emotion detection


class ConversationManager:
    def __init__(self, max_turns: int = 40) -> None:
        self.turns: List[Turn] = []
        self.max_turns = max_turns
        self.context: Dict[str, Any] = {
            "task": None, "project": None, "capability": None, "workflow": None}
        self.speaking = False

    # ------------------------------------------------------------- history

    def add_user(self, text: str, speaker: str = "owner") -> Turn:
        turn = Turn("user", text, speaker=speaker)
        self._append(turn)
        return turn

    def add_origami(self, text: str, tool: Optional[str] = None) -> Turn:
        turn = Turn("origami", text, tool=tool)
        self._append(turn)
        if tool:
            self.context["capability"] = tool.split(".", 1)[0]
        return turn

    def _append(self, turn: Turn) -> None:
        self.turns.append(turn)
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def history(self, limit: int = 6) -> List[Dict[str, Any]]:
        return [{"role": t.role, "text": t.text, "tool": t.tool, "at": t.at}
                for t in self.turns[-limit:]]

    def last_user_text(self) -> str:
        for t in reversed(self.turns):
            if t.role == "user":
                return t.text
        return ""

    # ------------------------------------------------------------- context

    def note_context(self, text: str, tool: Optional[str]) -> None:
        """Remember what we're on, so follow-ups don't need repeating."""
        low = text.lower()
        if tool:
            family = tool.split(".", 1)[0]
            self.context["capability"] = family
            if family in ("code", "projects"):
                m = re.search(r"\b(scan|open|start|explain)\s+([\w.-]{2,})", low)
                if m:
                    self.context["project"] = m.group(2)
            if family in ("reminder", "goal"):
                self.context["task"] = text[:60]

    def resolve(self, text: str) -> str:
        """Fill obvious pronouns from context ('explain it' -> 'explain <project>')."""
        low = text.lower().strip()
        project = self.context.get("project")
        if project and re.search(r"\b(it|that|this one|the project|the repo)\b", low):
            return re.sub(r"\b(it|that|this one|the project|the repo)\b", project, text,
                          count=1, flags=re.IGNORECASE)
        return text

    # -------------------------------------------------------- interruption

    @staticmethod
    def interruption(text: str) -> Optional[str]:
        low = text.lower().strip(" .!?,")
        if low in INTERRUPTS:
            return INTERRUPTS[low]
        for phrase, action in INTERRUPTS.items():
            if low.startswith(phrase + " ") or low == phrase:
                return action
        return None

    @staticmethod
    def is_ending(text: str) -> bool:
        low = text.lower().strip(" .!?,")
        return low in ENDINGS

    # ---------------------------------------------------------- speakable

    @staticmethod
    def speakable(text: str, limit: int = 420) -> str:
        """Turn tool output into something that sounds natural aloud."""
        if not text:
            return ""
        out = _TOOL_PREFIX.sub("", text.strip())
        out = _EMOJI.sub("", out)
        out = out.replace("✓", "").replace("✗", "").replace("→", ", ")
        out = _MARKUP.sub("", out)
        lines = [ln.strip(" -•\t") for ln in out.splitlines() if ln.strip()]
        out = ". ".join(lines)
        out = re.sub(r"\s+", " ", out).strip(" .")
        if len(out) > limit:                       # don't monologue
            cut = out[:limit].rsplit(".", 1)[0]
            out = (cut or out[:limit]) + ". There's more on screen."
        return out
