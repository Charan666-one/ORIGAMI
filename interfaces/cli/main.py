"""CLI surface — `origami "play some lofi"`.

Turns argv into a Goal, runs it through the orchestrator, prints the summary.
For non-SAFE tools it prompts the human (CONFIRM = y/n; CRITICAL = type the tool
name). SAFE tools like playing music never prompt.
"""

from __future__ import annotations

import asyncio
import itertools
import sys
import time

from core.schemas.goal import Goal
from core.schemas.plan import Step
from core.schemas.tool import Risk, ToolSpec


async def _with_spinner(coro):
    """Show an animated 'working' indicator on stderr while a command runs, so slow
    brain calls never look frozen. Cleared before the result prints."""
    async def spin():
        start = time.monotonic()
        for frame in itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"):
            sys.stderr.write(f"\r{frame} working… {time.monotonic() - start:4.1f}s")
            sys.stderr.flush()
            await asyncio.sleep(0.1)

    spinner = asyncio.ensure_future(spin())
    try:
        return await coro
    finally:
        spinner.cancel()
        sys.stderr.write("\r\033[K")  # clear the spinner line
        sys.stderr.flush()


def _load_env() -> None:
    """Load a repo-root .env if present so SPOTIFY_* etc. are available. Optional —
    absence is fine (the slice still runs keyless)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


async def _cli_confirmer(spec: ToolSpec, step: Step) -> bool:
    sys.stderr.write("\r\033[K")  # clear any spinner line before prompting
    sys.stderr.flush()
    if spec.risk is Risk.CRITICAL:
        print(f"🔴 CRITICAL: {spec.name} — {spec.description}")
        answer = input(f"   Type the tool name '{spec.name}' to approve: ").strip()
        return answer == spec.name
    print(f"🟡 CONFIRM: {spec.name} — {spec.description}  args={step.args}")
    return input("   Proceed? [y/N]: ").strip().lower() in ("y", "yes")


def _help_text() -> str:
    """Auto-generated from the live registry, so it never goes stale."""
    from main import build_orchestrator

    groups: dict[str, list] = {}
    for spec in build_orchestrator().executor.registry.all():
        groups.setdefault(spec.name.split(".", 1)[0], []).append(spec)

    icons = {"spotify": "🎵", "youtube": "▶️", "desktop": "🖥️", "terminal": "💻",
             "email": "📧", "reminder": "⏰", "goal": "🎯", "memory": "🧠",
             "calendar": "📅", "research": "🔎", "github": "🐙", "code": "📦",
             "project": "🚀", "profile": "👤", "assistant": "💬", "brief": "📋"}
    risk_mark = {"confirm": " 🟡", "critical": " 🔴"}

    lines = ['ORIGAMI — say what you want:  origami "<request>"', ""]
    for group in sorted(groups):
        specs = groups[group]
        lines.append(f"{icons.get(group, '•')} {group}")
        for s in specs:
            example = s.keywords[0].strip() if s.keywords else s.name
            mark = risk_mark.get(getattr(s.risk, "value", ""), "")
            lines.append(f"   {example:<24} {s.description}{mark}")
        lines.append("")
    lines.append("🟡 asks to confirm · 🔴 needs explicit approval")
    lines.append('Also: origami monitor   (background reminders + follow-ups)')
    return "\n".join(lines)


def _cloud_consent(provider_name: str, task) -> bool:
    """Asked before ORIGAMI uses any cloud model — it never auto-depends on one."""
    print(f"☁️  The local model can't handle this. Use cloud provider '{provider_name}'?")
    return input("   This sends your request off-device. Proceed? [y/N]: ").strip().lower() in ("y", "yes")


def main() -> int:
    _load_env()
    args = sys.argv[1:]

    if args and args[0] == "monitor":
        from interfaces.cli.monitor import run_monitor
        return run_monitor()

    text = " ".join(args).strip()
    if not text or text.lower() in ("help", "--help", "-h", "what can you do"):
        print(_help_text())
        return 0 if text else 2

    from main import build_orchestrator  # composition root (repo-root main.py)

    orchestrator = build_orchestrator(confirmer=_cli_confirmer, cloud_consent=_cloud_consent)
    result = asyncio.run(_with_spinner(orchestrator.handle(Goal(text=text, source="cli"))))
    print(result.summary)
    if result.learned:
        print(f"🧠 (learned: {'; '.join(result.learned)})")
    return 0 if result.success or not result.steps else 1


if __name__ == "__main__":
    raise SystemExit(main())
