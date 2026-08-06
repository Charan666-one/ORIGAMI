"""User profile — persistence and routing."""

from __future__ import annotations

from core.schemas.goal import Goal
from engines.memory.profile import UserProfile
from main import build_orchestrator


def test_profile_load_and_save(tmp_path):
    p = UserProfile(path=tmp_path / "profile.md")
    assert p.load() == ""
    p.save("I am Charan, a CSE-AIML student.")
    assert "Charan" in p.load()


async def test_profile_show_routes(tmp_path):
    orch = build_orchestrator()
    plan = await orch.planner.plan(Goal(text="show my profile"))
    assert plan.steps[0].tool == "profile.show"
