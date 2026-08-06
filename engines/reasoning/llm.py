"""Brain Interface — the one contract every reasoning provider implements.

"The AI model is NOT ORIGAMI." A model is a replaceable engine behind this
interface. The Planner and skills only ever call task-shaped methods —
`reason / generate / summarize / code` — and never know which model answered.

Every provider implements just `complete()`; the task methods have default
implementations that frame the prompt and call `complete()`. `plan()` needs no
model at all (keyword routing) — that is the "if no AI is needed, execute
directly" rule baked into the interface.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, List

from core.schemas.goal import Goal
from core.schemas.plan import Plan, Step
from core.schemas.tool import ToolSpec


class Task(str, Enum):
    """What kind of thinking a call needs — drives model selection."""
    PLAN = "plan"            # route a goal to a tool (no AI needed)
    REASON = "reason"        # general reasoning / Q&A
    GENERATE = "generate"    # write content (emails, text)
    SUMMARIZE = "summarize"  # condense text
    CODE = "code"            # write/explain code


class Level(str, Enum):
    """Minimum intelligence a request needs — 'use the least that works'."""
    L0 = "L0-deterministic"  # no AI at all (handled by non-brain skills)
    L1 = "L1-fast"           # lightweight local model — instant, simple asks
    L2 = "L2-standard"       # standard local reasoning — coding, long writing
    L3 = "L3-advanced"       # cloud — only if local insufficient, with consent


_ADVANCED_HINTS = ("in depth", "in-depth", "comprehensive", "deep research",
                   "thorough", "use cloud", "use claude", "use gpt", "best model",
                   "think hard", "very detailed")
_STANDARD_HINTS = ("essay", "detailed", "long email", "research", "documentation",
                   "planning", "step by step", "step-by-step", "analyze", "analysis",
                   "explain in detail", "write code", "function", "script", "program")
_FAST_HINTS = ("quick", "short", "simple", "brief", "one line", "one-line",
               "tldr", "tl;dr", "a line")


def classify_level(task: "Task", text: str) -> "Level":
    """Pick the smallest capable level for a brain request (decision rule #2)."""
    t = (text or "").lower()
    words = len(t.split())
    if any(h in t for h in _ADVANCED_HINTS):
        return Level.L3
    if task is Task.CODE:
        return Level.L2
    if any(h in t for h in _STANDARD_HINTS) or words > 40:
        return Level.L2
    if any(h in t for h in _FAST_HINTS) or words <= 20:
        return Level.L1
    return Level.L2  # medium-length, unclassified -> standard reasoning


@dataclass
class LLMResponse:
    text: str
    model: str = ""
    raw: Any = None


class LLMEngine(ABC):
    """Common interface for all reasoning backends (local, cloud, echo)."""

    name: str = "base"
    is_cloud: bool = False

    @abstractmethod
    async def complete(self, prompt: str, task: "Task" = Task.REASON, **kwargs) -> LLMResponse:
        """Raw completion for a task. The only method a provider must implement."""

    def is_available(self) -> bool:
        """Whether this provider can serve a request right now (server up, key set)."""
        return True

    def can_think(self) -> bool:
        """Whether this provider can actually reason/generate (False = placeholder)."""
        return True

    # --- task-shaped convenience methods (default framing over complete) --------

    async def reason(self, prompt: str, **kwargs) -> str:
        r = await self.complete(prompt, task=Task.REASON, **kwargs)
        return r.text.strip()

    async def generate(self, instruction: str, **kwargs) -> str:
        prompt = ("Write the requested content. Return only the content itself, "
                  f"no preamble.\n\n{instruction}")
        r = await self.complete(prompt, task=Task.GENERATE, **kwargs)
        return r.text.strip()

    async def summarize(self, text: str, **kwargs) -> str:
        r = await self.complete(f"Summarize concisely:\n\n{text}", task=Task.SUMMARIZE, **kwargs)
        return r.text.strip()

    async def code(self, instruction: str, **kwargs) -> str:
        r = await self.complete(f"Write code for:\n\n{instruction}", task=Task.CODE, **kwargs)
        return r.text.strip()

    # --- planning needs no model: keyword routing -------------------------------

    async def plan(self, goal: Goal, tools: List[ToolSpec]) -> Plan:
        return keyword_match_plan(goal, tools)


def keyword_match_plan(goal: Goal, tools: List[ToolSpec]) -> Plan:
    """Pick the first tool whose keyword appears in the goal text. Generic: a new
    tool becomes reachable just by declaring keywords + a first param."""
    text_lower = goal.text.lower().strip()
    for spec in tools:
        for kw in spec.keywords:
            if kw.lower() in text_lower:
                args = {}
                if spec.params:
                    first_param = next(iter(spec.params))
                    args[first_param] = _residual(goal.text, kw) or goal.text
                return Plan(
                    goal=goal,
                    steps=[Step(tool=spec.name, args=args, reason=f"matched '{kw}'")],
                )
    return Plan(goal=goal, steps=[])


def _residual(text: str, keyword: str) -> str:
    """Text after removing the matched keyword (case-insensitive), preserving the
    case of the rest. No filler-word stripping — it would corrupt shell commands
    and filenames (e.g. 'a.txt')."""
    remainder = re.sub(re.escape(keyword), " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", remainder).strip()
