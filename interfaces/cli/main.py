"""CLI surface — `origami "play some lofi"`.

Turns argv into a Goal, runs it through the orchestrator, prints the summary.
For non-SAFE tools it prompts the human (CONFIRM = y/n; CRITICAL = type the tool
name). SAFE tools like playing music never prompt.
"""

from __future__ import annotations

import asyncio
import sys

from core.schemas.goal import Goal
from core.schemas.plan import Step
from core.schemas.tool import Risk, ToolSpec


async def _cli_confirmer(spec: ToolSpec, step: Step) -> bool:
    if spec.risk is Risk.CRITICAL:
        print(f"🔴 CRITICAL: {spec.name} — {spec.description}")
        answer = input(f"   Type the tool name '{spec.name}' to approve: ").strip()
        return answer == spec.name
    print(f"🟡 CONFIRM: {spec.name} — {spec.description}  args={step.args}")
    return input("   Proceed? [y/N]: ").strip().lower() in ("y", "yes")


def main() -> int:
    text = " ".join(sys.argv[1:]).strip()
    if not text:
        print('Usage: origami "<what you want>"   e.g. origami "play some lofi"')
        return 2

    from main import build_orchestrator  # composition root (repo-root main.py)

    orchestrator = build_orchestrator(confirmer=_cli_confirmer)
    result = asyncio.run(orchestrator.handle(Goal(text=text, source="cli")))
    print(result.summary)
    return 0 if result.success or not result.steps else 1


if __name__ == "__main__":
    raise SystemExit(main())
