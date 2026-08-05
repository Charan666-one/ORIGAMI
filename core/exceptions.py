"""OrigamiError hierarchy — one root so callers can catch all ORIGAMI errors."""

from __future__ import annotations


class OrigamiError(Exception):
    """Root of all ORIGAMI-raised errors."""


class PlanningError(OrigamiError):
    """The planner could not turn a goal into a plan."""


class ToolNotFound(OrigamiError):
    """A plan referenced a tool that is not in the registry."""


class ExecutionError(OrigamiError):
    """A tool raised while executing."""


class ApprovalDeclined(OrigamiError):
    """A CONFIRM/CRITICAL step was not approved by the user."""
