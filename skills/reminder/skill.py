"""ReminderSkill — schedule time-based reminders that the monitor fires.

`reminder.set` parses a time out of plain English and schedules it; `reminder.list`
shows pending ones; `reminder.done` marks one complete (grows your streak). All
SAFE (local). The `origami monitor` process is what actually notifies you.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, List

from core.schemas.tool import Risk, ToolSpec
from engines.planning.timeparse import parse_when
from skills.base import Skill

_IMPORTANT = ("important", "urgent", "critical", "must ")
# residual (keyword "change" already stripped): "<old> [reminder|one|task] to <new>"
_CHANGE = re.compile(r"^(.+?)\s+(?:reminder\s+|one\s+|task\s+)?to\s+(.+)$", re.IGNORECASE)
_STRIP = re.compile(r"^(the|my)\s+|\s+(reminder|one|task)$", re.IGNORECASE)


class ReminderSkill(Skill):
    def __init__(self, scheduler: Any) -> None:
        self.scheduler = scheduler

    def specs(self) -> List[ToolSpec]:
        # list first: its specific phrases must win before set's broad "reminder"
        return [
            ToolSpec(
                name="reminder.list",
                description="List pending reminders and your streak.",
                risk=Risk.SAFE,
                keywords=("my reminders", "list reminders", "what are my reminders",
                          "my tasks", "my schedule", "what's my streak", "my streak"),
            ),
            ToolSpec(
                name="reminder.change",
                description="Change the text of an existing reminder (keeps its time).",
                params={"text": "which reminder, and the new wording"},
                risk=Risk.SAFE,
                # before set: "change X reminder to Y" contains "reminder" (a set kw)
                keywords=("change ", "update reminder", "edit reminder", "rename "),
            ),
            ToolSpec(
                name="reminder.set",
                description="Schedule a reminder for a specific time.",
                params={"text": "what to be reminded of, and when"},
                risk=Risk.SAFE,
                keywords=("remind me", "reminder", "remind ", "schedule "),
            ),
            ToolSpec(
                name="reminder.done",
                description="Mark a task done (keeps your streak going).",
                params={"text": "which task you finished"},
                risk=Risk.SAFE,
                keywords=("mark done", "i finished", "i did", "completed ", "done ",
                          "i've done", "finished "),
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        if tool == "reminder.set":
            return self._set((kwargs.get("text") or "").strip())
        if tool == "reminder.list":
            return self._list()
        if tool == "reminder.change":
            return self._change((kwargs.get("text") or "").strip())
        if tool == "reminder.done":
            return self._done((kwargs.get("text") or "").strip())
        raise ValueError(f"Unknown tool: {tool}")

    def _set(self, text: str) -> str:
        parsed = parse_when(text)
        if parsed is None:
            return ("When should I remind you? Try 'remind me to submit at 5pm' "
                    "or 'in 30 minutes'.")
        due, task = parsed
        task = task or text
        important = any(w in text.lower() for w in _IMPORTANT)
        self.scheduler.add(task, due, important=important)
        when = datetime.fromtimestamp(due).strftime("%a %d %b, %I:%M %p").lstrip("0")
        star = " ⭐(important)" if important else ""
        return (f"⏰ Reminder set: \"{task}\" at {when}{star}.\n"
                f"Keep `origami monitor` running so I can nudge you.")

    def _list(self) -> str:
        pending = self.scheduler.pending()
        head = f"🔥 Streak: {self.scheduler.streak}\n"
        if not pending:
            return head + "No pending reminders."
        lines = []
        for t in pending:
            when = datetime.fromtimestamp(t.due).strftime("%a %I:%M %p").lstrip("0")
            lines.append(f"- {t.text}  ({when}){'  ⭐' if t.important else ''}")
        return head + "Pending:\n" + "\n".join(lines)

    def _change(self, text: str) -> str:
        m = _CHANGE.match(text)
        if not m:
            return ("To change a reminder, say e.g. "
                    "'change the rent reminder to get the job you want'.")
        old = _STRIP.sub("", m.group(1).strip()).strip()
        new = m.group(2).strip()
        task = self.scheduler.change(old, new)
        if task is None:
            return f"I couldn't find a pending reminder matching '{old}'."
        when = datetime.fromtimestamp(task.due).strftime("%a %I:%M %p").lstrip("0")
        return f"✏️ Updated: now \"{task.text}\" ({when})."

    def _done(self, text: str) -> str:
        task = self.scheduler.mark_done(text)
        if task is None:
            return f"I couldn't find a pending task matching '{text}'."
        return f"✅ Done: \"{task.text}\" — streak is now {self.scheduler.streak}! 🔥"
