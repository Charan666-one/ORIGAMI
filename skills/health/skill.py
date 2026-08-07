"""HealthSkill — ask ORIGAMI about its own architectural health.

Exposes the Project Health Engine: a summary check, a full audit, and per-
capability cards. Read-only by construction (the engine only analyses), so all
tools are SAFE.
"""

from __future__ import annotations

from typing import Any, List, Optional

from core.schemas.tool import Risk, ToolSpec
from engines.health.engine import ProjectHealthEngine
from skills.base import Skill


class HealthSkill(Skill):
    def __init__(self, engine: Optional[ProjectHealthEngine] = None) -> None:
        self.engine = engine or ProjectHealthEngine()

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="health.audit",
                description="Full architecture audit: scores, integration readiness, scalability.",
                risk=Risk.SAFE,
                keywords=("architecture audit", "full health", "health audit",
                          "audit the project", "weekly audit", "deep health"),
            ),
            ToolSpec(
                name="health.capabilities",
                description="Per-capability health cards.",
                risk=Risk.SAFE,
                keywords=("capability health", "health of my skills", "skill health",
                          "capabilities health"),
            ),
            ToolSpec(
                name="health.check",
                description="Project health summary: scores, warnings, recommendations.",
                risk=Risk.SAFE,
                keywords=("health check", "project health", "how healthy",
                          "is the project healthy", "health"),
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        report = self.engine.run()
        if tool == "health.check":
            return self.engine.render(report, detail="summary")
        if tool == "health.audit":
            return self.engine.render(report, detail="full")
        if tool == "health.capabilities":
            return self.engine.render_capabilities(report)
        raise ValueError(f"Unknown tool: {tool}")
