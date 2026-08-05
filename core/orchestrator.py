"""Orchestrator — the composition of the lifecycle for one goal:

    context → plan → execute (with risk gate + verification) → remember

It owns no business logic and imports no concrete skill/engine — everything is
injected. This is the single entry point a surface (CLI/API) calls.
"""

from __future__ import annotations

from typing import Optional

from core.context import ContextBuilder
from core.planner import Planner
from core.executor import Executor
from core.schemas.goal import Goal
from core.schemas.result import RunResult
from core.session import Session


class Orchestrator:
    def __init__(self, planner: Planner, executor: Executor,
                 context: Optional[ContextBuilder] = None,
                 session: Optional[Session] = None) -> None:
        self.planner = planner
        self.executor = executor
        self.context = context or ContextBuilder()
        self.session = session or Session()

    async def handle(self, goal: Goal) -> RunResult:
        goal = self.context.build(goal)
        plan = await self.planner.plan(goal)
        if plan.is_empty:
            result = RunResult(goal=goal, steps=[],
                               summary="I couldn't map that to a known tool yet.")
        else:
            result = await self.executor.run(plan)
        self.session.record(result)
        return result
