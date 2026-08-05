"""Planner — turns a Goal into a Plan by asking the reasoning engine.

Core stays free of any concrete engine/registry import: both are injected and
used by duck typing. The engine owns the planning strategy (keyword match for
Echo; real reasoning + keyword fallback for an LLM).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.schemas.goal import Goal
from core.schemas.plan import Plan

if TYPE_CHECKING:  # hints only — no runtime dependency on other layers
    from engines.reasoning.llm import LLMEngine
    from skills.registry import ToolRegistry


class Planner:
    def __init__(self, engine: "LLMEngine", registry: "ToolRegistry") -> None:
        self.engine = engine
        self.registry = registry

    async def plan(self, goal: Goal) -> Plan:
        return await self.engine.plan(goal, self.registry.all())
