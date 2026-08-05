"""Brain Interface — the one contract every reasoning model implements.

"The AI model is NOT ORIGAMI." A model is a replaceable engine behind this
interface (Echo now; Ollama/GPT/Claude/Gemini later) — swapping one requires
zero architectural redesign.

`plan()` has a concrete default: keyword matching over each tool's declared
keywords. EchoEngine uses it as-is (keyless, offline). A real LLM engine
overrides `plan()` and can call `super().plan()` as a fallback when its output
is unusable — that is the planner's "LLM plan + keyword fallback".
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List

from core.schemas.goal import Goal
from core.schemas.plan import Plan, Step
from core.schemas.tool import ToolSpec


@dataclass
class LLMResponse:
    text: str
    raw: Any = None


class LLMEngine(ABC):
    """Common interface for all reasoning backends."""

    name: str = "base"

    @abstractmethod
    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        """Free-form text completion."""

    async def plan(self, goal: Goal, tools: List[ToolSpec]) -> Plan:
        """Default plan: keyword-match the goal to a single tool."""
        return keyword_match_plan(goal, tools)


def keyword_match_plan(goal: Goal, tools: List[ToolSpec]) -> Plan:
    """Pick the first tool whose keyword appears in the goal text.

    Generic on purpose: a new tool becomes reachable just by declaring keywords
    and (optionally) a `query` param — no engine or core edits required.
    """
    text = goal.text.lower().strip()
    for spec in tools:
        for kw in spec.keywords:
            if kw.lower() in text:
                args = {}
                if "query" in spec.params:
                    args["query"] = _residual(text, kw) or goal.text
                return Plan(
                    goal=goal,
                    steps=[Step(tool=spec.name, args=args, reason=f"matched '{kw}'")],
                )
    return Plan(goal=goal, steps=[])


def _residual(text: str, keyword: str) -> str:
    """Text left after removing the matched keyword and common filler words."""
    remainder = text.replace(keyword.lower(), " ")
    remainder = re.sub(r"\b(some|the|a|an|please|for me|to)\b", " ", remainder)
    return re.sub(r"\s+", " ", remainder).strip()
