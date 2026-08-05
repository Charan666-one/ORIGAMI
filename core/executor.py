"""Executor — runs a Plan's steps through the registry, enforcing the risk gate
and running a Verification stage after each step.

Risk gate (PURPOSE.md 3-tier model):
  - SAFE     → runs immediately
  - CONFIRM  → asks the confirmer for approval
  - CRITICAL → asks the confirmer for *explicit* (typed) approval
A declined step is skipped, not failed, and later steps still run.

The confirmer is injected so the CLI can prompt a human while tests inject an
auto-approve / auto-decline function — no I/O in the core.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Awaitable, Callable

from core.events import Event, EventTypes, event_bus
from core.schemas.plan import Plan, Step
from core.schemas.result import RunResult, StepResult
from core.schemas.tool import Risk, ToolSpec

if TYPE_CHECKING:
    from skills.registry import ToolRegistry

# A confirmer decides whether a non-SAFE step may run.
Confirmer = Callable[[ToolSpec, Step], Awaitable[bool]]


async def deny_all(spec: ToolSpec, step: Step) -> bool:
    """Safe default when no confirmer is provided: never approve consequences."""
    return False


class Executor:
    def __init__(self, registry: "ToolRegistry", confirmer: Confirmer | None = None,
                 bus=event_bus) -> None:
        self.registry = registry
        self.confirmer = confirmer or deny_all
        self.bus = bus

    async def run(self, plan: Plan) -> RunResult:
        results: list[StepResult] = []
        for step in plan.steps:
            results.append(await self._run_step(step))
        return RunResult(goal=plan.goal, steps=results, summary=_summarize(results))

    async def _run_step(self, step: Step) -> StepResult:
        spec = self.registry.get(step.tool)

        if spec.risk is not Risk.SAFE:
            approved = await self.confirmer(spec, step)
            if not approved:
                return StepResult(step=step, success=False, skipped=True,
                                  error=f"{spec.risk.value} step declined")

        try:
            output = await self.registry.call(step.tool, **step.args)
        except Exception as exc:  # graceful degradation — a tool failure is data
            await self.bus.publish(Event(EventTypes.SKILL_FAILED,
                                          {"tool": step.tool, "error": str(exc)}))
            return StepResult(step=step, success=False, error=str(exc))

        verified = self._verify(spec, output)
        await self.bus.publish(Event(EventTypes.SKILL_EXECUTED,
                                      {"tool": step.tool, "verified": verified}))
        return StepResult(step=step, success=True, output=output, verified=verified)

    @staticmethod
    def _verify(spec: ToolSpec, output) -> bool:
        """Verification stage (trivial in C1): the tool returned without error and,
        if it was expected to yield something, did. Grows into real checks later."""
        return output is not None or spec.risk is Risk.SAFE


def _summarize(results: list[StepResult]) -> str:
    if not results:
        return "I couldn't map that to a known tool yet."
    lines = []
    for r in results:
        if r.skipped:
            lines.append(f"⏭  {r.step.tool} — skipped ({r.error})")
        elif r.success:
            detail = f" → {r.output}" if r.output is not None else ""
            lines.append(f"✓ {r.step.tool}{detail}")
        else:
            lines.append(f"✗ {r.step.tool} — {r.error}")
    return "\n".join(lines)
