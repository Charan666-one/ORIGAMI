"""Skill — base class for a capability that exposes one or more tools.

A skill declares its tools via `specs()` (each a ToolSpec, including its Risk
tier) and runs them via `execute(tool, **kwargs)`. Skills wrap adapters; they
never reimplement API clients, and they never call each other — only the
workflow/executor coordinates them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List

from core.schemas.tool import ToolSpec


class Skill(ABC):
    """Base class for all skills."""

    @abstractmethod
    def specs(self) -> List[ToolSpec]:
        """Return the tools this skill provides (name, risk, keywords, ...)."""

    @abstractmethod
    async def execute(self, tool: str, **kwargs) -> Any:
        """Run one of this skill's tools by name. Raise on failure."""
