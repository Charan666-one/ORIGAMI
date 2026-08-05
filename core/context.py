"""ContextBuilder — the Context stage of the lifecycle.

Thin in C1 (returns the goal unchanged). It is the seam where memory, time,
active project, and user preferences get folded into a goal in later checkpoints.
"""

from __future__ import annotations

from core.schemas.goal import Goal


class ContextBuilder:
    def build(self, goal: Goal) -> Goal:
        return goal
