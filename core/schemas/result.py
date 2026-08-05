"""Results — what execution produces. Includes the Verification stage flag."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from core.schemas.goal import Goal
from core.schemas.plan import Step


@dataclass
class StepResult:
    """Outcome of a single step, including whether it was verified or skipped."""

    step: Step
    success: bool
    output: Any = None
    error: Optional[str] = None
    verified: bool = False   # Verification stage: did the action achieve intent?
    skipped: bool = False    # user declined a CONFIRM/CRITICAL step


@dataclass
class RunResult:
    """Outcome of a whole goal: the steps and a human-readable summary."""

    goal: Goal
    steps: List[StepResult] = field(default_factory=list)
    summary: str = ""

    @property
    def success(self) -> bool:
        """True only if every non-skipped step succeeded and at least one ran."""
        ran = [s for s in self.steps if not s.skipped]
        return bool(ran) and all(s.success for s in ran)
