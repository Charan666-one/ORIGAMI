"""Core dataclasses — the lingua franca shared across every layer."""

from core.schemas.goal import Goal
from core.schemas.tool import Risk, ToolSpec
from core.schemas.plan import Plan, Step
from core.schemas.result import RunResult, StepResult

__all__ = [
    "Goal",
    "Risk",
    "ToolSpec",
    "Plan",
    "Step",
    "RunResult",
    "StepResult",
]
