"""Daily brief + codebase forget + auto-generated help."""

from __future__ import annotations

import time

from core.schemas.goal import Goal
from engines.knowledge.codebases import CodebaseStore
from engines.planning.goals import GoalBook
from engines.planning.scheduler import Scheduler
from main import build_orchestrator
from skills.brief.skill import BriefSkill
from skills.code.skill import CodeSkill


async def test_brief_aggregates_everything(tmp_path):
    sched = Scheduler(path=tmp_path / "t.json")
    sched.add("submit report", time.time() + 3600, important=True)
    goals = GoalBook(path=tmp_path / "g.json")
    goals.add("get an internship", ["polish resume", "practice DSA"])
    cb = CodebaseStore(path=tmp_path / "cb.json")
    cb.save("origami", {"summary": "s"})

    out = await BriefSkill(scheduler=sched, goals=goals, codebases=cb).execute("brief.today")
    assert "submit report" in out and "⭐" in out       # reminder + important flag
    assert "get an internship" in out and "0/2" in out  # goal + progress
    assert "polish resume" in out                        # next step
    assert "origami" in out                              # learned codebases


async def test_brief_empty_state(tmp_path):
    out = await BriefSkill(scheduler=Scheduler(path=tmp_path / "t.json"),
                           goals=GoalBook(path=tmp_path / "g.json"),
                           codebases=CodebaseStore(path=tmp_path / "c.json")
                           ).execute("brief.today")
    assert "No pending reminders" in out and "No active goals" in out


async def test_forget_codebase(tmp_path):
    store = CodebaseStore(path=tmp_path / "cb.json")
    store.save("oldproj", {"summary": "x"})
    skill = CodeSkill(brain=None, store=store)

    assert "Forgot" in await skill.execute("code.forget", text="oldproj")
    assert store.get("oldproj") is None
    assert "don't have" in await skill.execute("code.forget", text="nope")


async def test_brief_routes():
    orch = build_orchestrator()
    for text in ("my brief", "what's my day", "daily brief"):
        plan = await orch.planner.plan(Goal(text=text))
        assert plan.steps[0].tool == "brief.today", f"{text!r}"


def test_help_lists_all_skill_groups():
    from interfaces.cli.main import _help_text
    text = _help_text()
    for group in ("spotify", "reminder", "goal", "github", "code", "brief"):
        assert group in text
    assert "🟡" in text  # risk legend
