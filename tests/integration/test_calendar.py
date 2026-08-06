"""Calendar skill + native macOS adapter (keyless, mocked runner)."""

from __future__ import annotations

from datetime import datetime

from adapters.calendar.mac import MacCalendar
from core.schemas.goal import Goal
from main import build_orchestrator
from skills.calendar.skill import CalendarSkill


class FakeCalendar:
    def __init__(self):
        self.added = None

    def add_event(self, title, when, minutes=60):
        self.added = (title, when)
        return when

    def events_today(self):
        return ["Standup @ 9:00:00 AM", "Lunch @ 1:00:00 PM"]


def test_mac_adapter_builds_locale_independent_applescript():
    seen = {}
    cal = MacCalendar(runner=lambda s: seen.setdefault("s", s) or "ok")
    cal.add_event('Dentist "checkup"', datetime(2026, 8, 20, 17, 0))
    s = seen["s"]
    assert "set year of d to 2026" in s and "set month of d to 8" in s
    assert "set hours of d to 17" in s
    assert 'summary:"Dentist \\"checkup\\""' in s   # quotes escaped


async def test_calendar_add_parses_time():
    fake = FakeCalendar()
    skill = CalendarSkill(calendar=fake)
    msg = await skill.execute("calendar.add", text="dentist appointment at 5pm")
    assert "dentist" in msg.lower()
    title, when = fake.added
    assert when.hour == 17


async def test_calendar_add_without_time_asks():
    skill = CalendarSkill(calendar=FakeCalendar())
    msg = await skill.execute("calendar.add", text="dentist appointment")
    assert "when" in msg.lower()


async def test_calendar_today_lists_events():
    skill = CalendarSkill(calendar=FakeCalendar())
    msg = await skill.execute("calendar.today")
    assert "Standup" in msg and "Lunch" in msg


async def test_calendar_routing():
    orch = build_orchestrator()
    for text, expected in {
        "add a meeting tomorrow at 3pm": "calendar.add",
        "add to my calendar dentist at 5pm": "calendar.add",
        "what's on my calendar": "calendar.today",
        "events today": "calendar.today",
    }.items():
        plan = await orch.planner.plan(Goal(text=text))
        assert plan.steps[0].tool == expected, f"{text!r} -> {plan.steps[0].tool}"
