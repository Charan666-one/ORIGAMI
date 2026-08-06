"""Goal Mode (C5) — create with brain-decomposed milestones, track progress, routing."""

from __future__ import annotations

from core.schemas.goal import Goal
from engines.planning.goals import GoalBook
from engines.reasoning.llm import LLMEngine, LLMResponse, Task
from main import build_orchestrator
from skills.goals.skill import GoalsSkill


class FakeBrain(LLMEngine):
    """Returns a numbered plan so goal.create can decompose it (keyless)."""
    def can_think(self) -> bool:
        return True

    async def complete(self, prompt, task=Task.REASON, **kwargs) -> LLMResponse:
        return LLMResponse(text="ok")

    async def generate(self, instruction, **kwargs) -> str:
        return ("1. Polish your resume\n2. Practice LeetCode daily\n"
                "3. Build two strong projects\n4. Get referrals\n5. Apply and interview")


async def test_create_decomposes_into_milestones(tmp_path):
    book = GoalBook(path=tmp_path / "goals.json")
    skill = GoalsSkill(goals=book, brain=FakeBrain())
    msg = await skill.execute("goal.create", text="get a Google internship")

    assert "Polish your resume" in msg
    goal = book.latest()
    assert goal is not None and len(goal.milestones) == 5
    assert goal.title.lower().startswith("get a google internship")


async def test_status_and_next_and_done(tmp_path):
    book = GoalBook(path=tmp_path / "goals.json")
    skill = GoalsSkill(goals=book, brain=FakeBrain())
    await skill.execute("goal.create", text="get a Google internship")

    assert "Next: Polish your resume" in await skill.execute("goal.next")

    done_msg = await skill.execute("goal.done", text="resume")
    assert "Polish your resume" in done_msg and "1/5" in done_msg

    status = await skill.execute("goal.status")
    assert "1/5" in status and "✅" in status


async def test_create_without_model_still_tracks(tmp_path):
    class NoBrain(FakeBrain):
        def can_think(self):
            return False
    book = GoalBook(path=tmp_path / "goals.json")
    skill = GoalsSkill(goals=book, brain=NoBrain())
    msg = await skill.execute("goal.create", text="learn the guitar")
    assert "Goal set" in msg
    assert book.latest().title == "learn the guitar"


async def test_routing(tmp_path):
    orch = build_orchestrator(goals=GoalBook(path=tmp_path / "goals.json"))
    cases = {
        "help me get a Google internship": "goal.create",
        "my goals": "goal.status",
        "what's next": "goal.next",
        "completed milestone": "goal.done",   # goals before reminder wins
    }
    for text, expected in cases.items():
        plan = await orch.planner.plan(Goal(text=text))
        assert plan.steps[0].tool == expected, f"{text!r} -> {plan.steps[0].tool}"


async def test_finished_report_still_routes_to_reminder(tmp_path):
    # regression: goal.done keywords must not steal reminder completion
    orch = build_orchestrator(goals=GoalBook(path=tmp_path / "goals.json"))
    plan = await orch.planner.plan(Goal(text="i finished the report"))
    assert plan.steps[0].tool == "reminder.done"
