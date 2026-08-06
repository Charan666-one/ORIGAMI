"""GoalsSkill — Goal Mode. State what you want; ORIGAMI tracks it as milestones.

`goal.create` uses the brain to decompose the objective into concrete steps;
`goal.status` reports progress; `goal.next` says what to focus on; `goal.done`
ticks off a milestone. Built on the goal store + the brain (both injected, so it
stays provider-independent). All SAFE.
"""

from __future__ import annotations

import re
from typing import Any, List

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill

_LIST_LINE = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s*(.+?)\s*$")
_GOAL_LEAD = re.compile(
    r"^(help me|i want to|i want|my goal is to|my goal is|set a goal to|"
    r"set a goal|new goal|goal)\b[:\s]*", re.IGNORECASE)


class GoalsSkill(Skill):
    def __init__(self, goals: Any, brain: Any) -> None:
        self.goals = goals
        self.brain = brain

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="goal.status",
                description="Show your goals and how far along each one is.",
                risk=Risk.SAFE,
                keywords=("my goals", "goal status", "goal progress", "my progress",
                          "how am i doing", "show my goals"),
            ),
            ToolSpec(
                name="goal.next",
                description="What to work on next toward your goal.",
                risk=Risk.SAFE,
                keywords=("what's next", "whats next", "next step", "what should i do next",
                          "what should i work on", "next on my goal"),
            ),
            ToolSpec(
                name="goal.done",
                description="Tick off a milestone on your goal.",
                params={"text": "which milestone (or leave blank for the next one)"},
                risk=Risk.SAFE,
                keywords=("milestone done", "completed milestone", "step done",
                          "finished a step", "tick off", "goal step done"),
            ),
            ToolSpec(
                name="goal.create",
                description="Start tracking a long-term goal, broken into milestones.",
                params={"text": "the goal"},
                risk=Risk.SAFE,
                keywords=("help me get", "help me become", "help me land", "help me achieve",
                          "my goal is", "i want to become", "i want to get", "set a goal",
                          "new goal", "goal:"),
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        if tool == "goal.create":
            return await self._create((kwargs.get("text") or "").strip())
        if tool == "goal.status":
            return self._status()
        if tool == "goal.next":
            return self._next()
        if tool == "goal.done":
            return self._done((kwargs.get("text") or "").strip())
        raise ValueError(f"Unknown tool: {tool}")

    # ------------------------------------------------------------------ helpers

    async def _create(self, text: str) -> str:
        title = _GOAL_LEAD.sub("", text).strip() or text
        milestones = await self._decompose(title)
        goal = self.goals.add(title, milestones)
        if not goal.milestones:
            return (f"🎯 Goal set: \"{title}\". I couldn't auto-plan the steps "
                    f"(needs a local model — see `ollama pull llama3.2:1b`).")
        steps = "\n".join(f"  {i}. {m.text}" for i, m in enumerate(goal.milestones, 1))
        return (f"🎯 New goal: \"{title}\" — here's the plan:\n{steps}\n"
                f"Say 'what's next' anytime, or 'step done' as you finish each.")

    async def _decompose(self, title: str) -> List[str]:
        if self.brain is None or not self.brain.can_think():
            return []
        try:
            reply = await self.brain.generate(
                f"Break this goal into 5-7 short, concrete, actionable steps: '{title}'. "
                f"Return ONLY a numbered list, one step per line, no preamble.")
            steps = [m.group(1) for line in reply.splitlines()
                     if (m := _LIST_LINE.match(line))]
            return steps[:8]
        except Exception:
            return []

    def _status(self) -> str:
        active = self.goals.active()
        if not active:
            return "No active goals yet. Try: 'help me get a Google internship'."
        blocks = []
        for g in active:
            done, total = g.progress()
            bar = "█" * done + "░" * (total - done) if total else ""
            lines = [f"🎯 {g.title}  [{bar}] {done}/{total}"]
            for i, m in enumerate(g.milestones, 1):
                lines.append(f"   {'✅' if m.done else '⬜'} {i}. {m.text}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def _next(self) -> str:
        goal = self.goals.latest()
        if goal is None:
            return "No active goals. Start one with 'help me <goal>'."
        opens = goal.next_open()
        if not opens:
            return f"🎉 You've completed every step of \"{goal.title}\"!"
        nxt = opens[0].text
        return f"🎯 {goal.title}\n👉 Next: {nxt}\n({len(opens)} step(s) left)"

    def _done(self, text: str) -> str:
        goal = self.goals.latest()
        if goal is None:
            return "No active goal to update."
        m = self.goals.complete_milestone(goal, text)
        if m is None:
            return "Nothing left to tick off on that goal."
        done, total = goal.progress()
        tail = " 🎉 Goal complete!" if done == total else ""
        return f"✅ {m.text}  ({done}/{total} done){tail}"
