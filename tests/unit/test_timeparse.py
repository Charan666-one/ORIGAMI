"""Natural-time parsing for reminders."""

from __future__ import annotations

from datetime import datetime

from engines.planning.timeparse import parse_when

NOON = datetime(2026, 1, 1, 12, 0, 0).timestamp()  # fixed reference: Thu Jan 1, noon


def test_relative_minutes():
    due, task = parse_when("submit the report in 30 minutes", NOON)
    assert abs(due - (NOON + 1800)) < 2
    assert "report" in task.lower()


def test_relative_hours():
    due, _ = parse_when("call back in 2 hours", NOON)
    assert abs(due - (NOON + 7200)) < 2


def test_at_pm_same_day():
    due, task = parse_when("call mom at 5pm", NOON)
    got = datetime.fromtimestamp(due)
    assert got.hour == 17 and got.day == 1
    assert "call mom" in task.lower()


def test_at_am_rolls_to_next_day():
    due, _ = parse_when("gym at 9am", NOON)  # 9am already passed at noon
    got = datetime.fromtimestamp(due)
    assert got.hour == 9 and got.day == 2


def test_tomorrow_at_time():
    due, task = parse_when("finish the essay tomorrow at 10am", NOON)
    got = datetime.fromtimestamp(due)
    assert got.day == 2 and got.hour == 10
    assert "essay" in task.lower()


def test_no_time_returns_none():
    assert parse_when("just do something", NOON) is None
