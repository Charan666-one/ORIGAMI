"""CalendarSkill — add events to and read the native macOS Calendar (keyless).

`calendar.add` parses a time and creates an event; `calendar.today` lists today's
events. SAFE (local calendar writes, reversible; no invites sent).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, List

from core.schemas.tool import Risk, ToolSpec
from engines.planning.timeparse import parse_when
from skills.base import Skill

# strip leading "a meeting called", "an event titled", "named", etc. from a title
_TITLE_LEAD = re.compile(
    r"^(a |an |the )?(meeting|appointment|event|call)?\s*(called|titled|named|with|for|about)?\s*",
    re.IGNORECASE)


class CalendarSkill(Skill):
    def __init__(self, calendar: Any = None) -> None:
        self._cal = calendar

    @property
    def cal(self):
        if self._cal is None:
            from adapters.calendar.mac import MacCalendar  # lazy import
            self._cal = MacCalendar()
        return self._cal

    def specs(self) -> List[ToolSpec]:
        # add before today: "add to my calendar ..." contains "my calendar" (a today kw)
        return [
            ToolSpec(
                name="calendar.add",
                description="Add an event to the calendar at a specific time.",
                params={"text": "the event and when"},
                risk=Risk.SAFE,
                keywords=("add to calendar", "add to my calendar", "add event",
                          "add a meeting", "put on my calendar", "new event",
                          "calendar event", "book a meeting", "add appointment"),
            ),
            ToolSpec(
                name="calendar.today",
                description="List today's calendar events.",
                risk=Risk.SAFE,
                keywords=("my calendar", "what's on my calendar", "whats on my calendar",
                          "calendar today", "events today", "what do i have today",
                          "today's events", "todays events"),
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        if tool == "calendar.add":
            return self._add((kwargs.get("text") or "").strip())
        if tool == "calendar.today":
            return self._today()
        raise ValueError(f"Unknown tool: {tool}")

    def _add(self, text: str) -> str:
        parsed = parse_when(text)
        if parsed is None:
            return ("When is it? e.g. 'add a meeting tomorrow at 3pm' or "
                    "'add dentist appointment at 5pm'.")
        due, title = parsed
        title = _TITLE_LEAD.sub("", title).strip() or title or "Event"
        when = datetime.fromtimestamp(due)
        try:
            self.cal.add_event(title, when)
        except Exception as exc:
            return (f"Couldn't add the event ({exc}). If macOS asks, grant ORIGAMI "
                    f"access to Calendar in System Settings → Privacy.")
        stamp = when.strftime("%a %d %b, %I:%M %p").lstrip("0")
        return f"📅 Added \"{title}\" to your calendar for {stamp}."

    def _today(self) -> str:
        try:
            events = self.cal.events_today()
        except Exception as exc:
            return f"Couldn't read the calendar ({exc})."
        if not events:
            return "📅 Nothing on your calendar today."
        return "📅 Today:\n" + "\n".join(f"- {e}" for e in events)
