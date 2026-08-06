"""ProfileSkill — view the persistent user profile ORIGAMI carries.

The profile itself is injected into every brain call (see main.py + BrainManager);
this skill just lets the user see it. Editing is done directly in the file
(~/.origami/profile.md) or by a future profile.set.
"""

from __future__ import annotations

from typing import Any, List

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill


class ProfileSkill(Skill):
    def __init__(self, profile: Any) -> None:
        self.profile = profile

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="profile.show",
                description="Show the persistent profile ORIGAMI keeps about you.",
                risk=Risk.SAFE,
                keywords=("my profile", "who am i to you", "show my profile",
                          "my context", "what's my profile"),
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        if tool == "profile.show":
            text = self.profile.load()
            if not text:
                return ("No profile set yet. Add one at ~/.origami/profile.md and I'll "
                        "use it in every answer.")
            return f"Here's what I know about you (from ~/.origami/profile.md):\n\n{text}"
        raise ValueError(f"Unknown tool: {tool}")
