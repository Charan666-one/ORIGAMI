"""Plan — the workflow the planner produces: an ordered list of tool calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from core.schemas.goal import Goal


@dataclass
class Step:
    """One tool invocation within a plan."""

    tool: str
    args: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class Plan:
    """A goal decomposed into steps. Empty steps == "nothing matched"."""

    goal: Goal
    steps: List[Step] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.steps
