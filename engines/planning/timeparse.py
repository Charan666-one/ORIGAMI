"""Lightweight natural-time parsing for reminders — no external deps.

parse_when("submit report tomorrow at 9am", now) -> (epoch, "submit report")
Handles: "in N minutes/hours", "at 5pm / 5:30pm / 17:00 / at 9", "tomorrow ...".
Returns None if no time is found.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

_REL = re.compile(r"\bin\s+(\d+)\s*(minutes?|mins?|min|hours?|hrs?|hr|h)\b", re.IGNORECASE)
_CLOCK = re.compile(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?", re.IGNORECASE)
_CLEAN = re.compile(r"\b(remind me to|remind me|reminder to|reminder|to|at|by|tomorrow|today)\b",
                    re.IGNORECASE)


def parse_when(text: str, now: Optional[float] = None) -> Optional[Tuple[float, str]]:
    base = datetime.fromtimestamp(now) if now is not None else datetime.now()
    low = text.lower()

    # 1) relative: "in 30 minutes", "in 2 hours"
    m = _REL.search(low)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        delta = timedelta(hours=n) if unit.startswith(("h",)) else timedelta(minutes=n)
        return (base + delta).timestamp(), _clean_task(text, m.span())

    days = 1 if "tomorrow" in low else 0

    # 2) clock time: needs an explicit signal (am/pm, "at ", or "tomorrow")
    for m in _CLOCK.finditer(low):
        hour = int(m.group(1))
        if hour > 23:
            continue
        has_ampm = bool(m.group(3))
        has_at = low[max(0, m.start() - 3):m.start()].endswith("at ")
        if not (has_ampm or has_at or days):
            continue
        minute = int(m.group(2) or 0)
        ampm = (m.group(3) or "").replace(".", "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        try:
            due = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            continue
        due += timedelta(days=days)
        if due <= base and days == 0:
            due += timedelta(days=1)  # time already passed today -> next occurrence
        return due.timestamp(), _clean_task(text, m.span())

    return None


def _clean_task(text: str, span) -> str:
    """Remove the time phrase and connective words to leave just the task."""
    without_time = text[:span[0]] + " " + text[span[1]:]
    cleaned = _CLEAN.sub(" ", without_time)
    return re.sub(r"\s+", " ", cleaned).strip(" .,-")
