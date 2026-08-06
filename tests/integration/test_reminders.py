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


async def test_change_reminder_text(tmp_path):
    sched = Scheduler(path=tmp_path / "t.json")
    skill = ReminderSkill(scheduler=sched)
    await skill.execute("reminder.set", text="pay rent tomorrow at 9am")
    msg = await skill.execute("reminder.change", text="the rent one to get the job you want")
    assert "get the job you want" in msg
    assert sched.pending()[0].text == "get the job you want"


async def test_change_routes(tmp_path):
    orch = build_orchestrator(scheduler=Scheduler(path=tmp_path / "t.json"))
    plan = await orch.planner.plan(Goal(text="change the rent one to get the job you want"))
    assert plan.steps[0].tool == "reminder.change"


async def test_change_routes_even_with_word_reminder(tmp_path):
    # regression: "change ... reminder ..." must not route to reminder.set
    orch = build_orchestrator(scheduler=Scheduler(path=tmp_path / "t.json"))
    plan = await orch.planner.plan(Goal(text="change the gym reminder to go for a run"))
    assert plan.steps[0].tool == "reminder.change"


async def test_cancel_reminder(tmp_path):
    sched = Scheduler(path=tmp_path / "t.json")
    skill = ReminderSkill(scheduler=sched)
    await skill.execute("reminder.set", text="pay the bills in 2 hours")
    msg = await skill.execute("reminder.cancel", text="bills")
    assert "cancelled" in msg.lower()
    assert sched.pending() == []


async def test_remind_me_to_run_is_a_reminder_not_terminal(tmp_path):
    # regression: the word "run" must not steal a reminder for terminal
    orch = build_orchestrator(scheduler=Scheduler(path=tmp_path / "t.json"))
    plan = await orch.planner.plan(Goal(text="remind me to run at 6am"))
    assert plan.steps[0].tool == "reminder.set"


async def test_cancel_routes(tmp_path):
    orch = build_orchestrator(scheduler=Scheduler(path=tmp_path / "t.json"))
    plan = await orch.planner.plan(Goal(text="cancel the gym reminder"))
    assert plan.steps[0].tool == "reminder.cancel"
