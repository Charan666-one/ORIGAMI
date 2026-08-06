"""Reminders (Monitoring Mode) — set, list, done, streak, routing."""

from __future__ import annotations

from core.schemas.goal import Goal
from engines.planning.scheduler import Scheduler
from main import build_orchestrator
from skills.reminder.skill import ReminderSkill


async def test_set_reminder_schedules_it(tmp_path):
    sched = Scheduler(path=tmp_path / "t.json")
    skill = ReminderSkill(scheduler=sched)
    msg = await skill.execute("reminder.set", text="submit the report in 2 hours")
    assert "Reminder set" in msg
    assert len(sched.pending()) == 1
    assert "report" in sched.pending()[0].text.lower()


async def test_set_without_time_asks_for_one(tmp_path):
    skill = ReminderSkill(scheduler=Scheduler(path=tmp_path / "t.json"))
    msg = await skill.execute("reminder.set", text="do the thing")
    assert "when" in msg.lower()


async def test_done_grows_streak(tmp_path):
    sched = Scheduler(path=tmp_path / "t.json")
    skill = ReminderSkill(scheduler=sched)
    await skill.execute("reminder.set", text="read chapter in 1 hour")
    msg = await skill.execute("reminder.done", text="chapter")
    assert "streak is now 1" in msg


async def test_important_reminder_flagged(tmp_path):
    sched = Scheduler(path=tmp_path / "t.json")
    skill = ReminderSkill(scheduler=sched)
    await skill.execute("reminder.set", text="important: pay rent tomorrow at 9am")
    assert sched.pending()[0].important


async def test_remind_routes_to_reminder(tmp_path):
    orch = build_orchestrator(scheduler=Scheduler(path=tmp_path / "t.json"))
    plan = await orch.planner.plan(Goal(text="remind me to call mom at 5pm"))
    assert plan.steps[0].tool == "reminder.set"


async def test_list_and_streak_route(tmp_path):
    orch = build_orchestrator(scheduler=Scheduler(path=tmp_path / "t.json"))
    plan = await orch.planner.plan(Goal(text="what are my reminders"))
    assert plan.steps[0].tool == "reminder.list"
