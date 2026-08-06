"""MemorySkill — teach ORIGAMI facts and recall them.

`memory.remember` stores a fact; `memory.recall` retrieves relevant ones. Both
SAFE (local, no consequence). The stored facts also silently enrich the AI brain
elsewhere (see AssistantSkill), so ORIGAMI answers with what it knows about you.
"""

from __future__ import annotations

import re
from typing import Any, List

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill

# strip a leading "that/to/:" so "remember that X" stores just "X"
_LEAD = re.compile(r"^(that|to|:|,|-|\s)+", re.IGNORECASE)


class MemorySkill(Skill):
    def __init__(self, memory: Any) -> None:
        self.memory = memory

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="memory.remember",
                description="Store a fact ORIGAMI should remember about you or your work.",
                params={"text": "the fact to remember"},
                risk=Risk.SAFE,
                keywords=("remember", "note that", "keep in mind", "don't forget",
                          "make a note"),
            ),
            ToolSpec(
                name="memory.recall",
                description="Recall what ORIGAMI knows about a topic.",
                params={"query": "the topic"},
                risk=Risk.SAFE,
                keywords=("recall", "what do you know", "what do you remember",
                          "remind me what", "what have i told you"),
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        if tool == "memory.remember":
            text = _LEAD.sub("", (kwargs.get("text") or "").strip())
            if not text:
                return "What should I remember?"
            self.memory.add(text, kind="fact")
            return f"Got it — I'll remember: {text}"
        if tool == "memory.recall":
            query = (kwargs.get("query") or "").strip()
            hits = self.memory.search(query, limit=5)
            if not hits:
                return f"I don't have anything stored about '{query}'."
            return "Here's what I remember:\n" + "\n".join(f"- {r.text}" for r in hits)
        raise ValueError(f"Unknown tool: {tool}")
