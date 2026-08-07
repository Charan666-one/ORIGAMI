"""BriefSkill — a one-glance daily dashboard: reminders, goals, streak, knowledge.

Aggregates existing local data (scheduler, goals, memory, codebases) — instant,
no model. This is the C6 'daily executive brief' in its deterministic form.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill


class BriefSkill(Skill):
    def __init__(self, scheduler: Any = None, goals: Any = None, codebases: Any = None) -> None:
        self.scheduler = scheduler
        self.goals = goals
        self.codebases = codebases

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="brief.today",
                description="Your daily brief: reminders, goals, streak at a glance.",
                risk=Risk.SAFE,
                keywords=("brief", "my day", "daily brief", "morning brief", "dashboard",
                          "what's my day", "whats my day", "overview of my day", "my overview"),
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        if tool != "brief.today":
            raise ValueError(f"Unknown tool: {tool}")
        lines = [f"📋 Brief — {datetime.now().strftime('%A %d %b, %I:%M %p').lstrip('0')}"]

        if self.scheduler is not None:
            lines.append(f"\n🔥 Streak: {self.scheduler.streak}")
            pending = self.scheduler.pending()
            if pending:
                lines.append("⏰ Upcoming:")
                for t in pending[:5]:
                    when = datetime.fromtimestamp(t.due).strftime("%a %I:%M %p").lstrip("0")
                    star = " ⭐" if getattr(t, "important", False) else ""
                    lines.append(f"   • {t.text} ({when}){star}")
            else:
                lines.append("⏰ No pending reminders.")

        if self.goals is not None:
            active = self.goals.active()
            if active:
                lines.append("\n🎯 Goals:")
                for g in active[:5]:
                    done, total = g.progress()
                    nxt = g.next_open()
                    tip = f" → next: {nxt[0].text}" if nxt else " ✓ complete"
                    lines.append(f"   • {g.title} [{done}/{total}]{tip}")
            else:
                lines.append("\n🎯 No active goals. Start one: 'help me <goal>'.")

        if self.codebases is not None:
            names = self.codebases.names()
            if names:
                lines.append(f"\n🧠 Learned codebases: {', '.join(names)}")

        return "\n".join(lines)
