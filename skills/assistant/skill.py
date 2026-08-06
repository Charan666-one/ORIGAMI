"""AssistantSkill — the thinking capability. Uses the Brain Interface to answer,
write, and summarize. Provider-independent: it depends only on the injected brain
(an LLMEngine), never on a specific model.

If no real model is available (Echo only), it says so and points to Ollama rather
than echoing nonsense — ORIGAMI never fabricates thinking it can't do.
"""

from __future__ import annotations

from typing import Any, List

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill

_NEEDS_MODEL = (
    "I need a local model to think about that. Install Ollama and pull a fast model:\n"
    "  brew install ollama && ollama serve\n"
    "  ollama pull llama3.2:3b\n"
    "Then ask me again — no API key, runs offline. (llama3.2:3b fits 8GB and is snappy.)"
)


class AssistantSkill(Skill):
    def __init__(self, brain: Any, memory: Any = None) -> None:
        self.brain = brain
        self.memory = memory  # optional: enriches answers with what ORIGAMI knows

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="assistant.write",
                description="Write content (essay, message, note) with the AI brain.",
                params={"prompt": "what to write"},
                risk=Risk.SAFE,
                keywords=("write ", "compose ", "draft "),
            ),
            ToolSpec(
                name="assistant.summarize",
                description="Summarize text with the AI brain.",
                params={"text": "the text to summarize"},
                risk=Risk.SAFE,
                keywords=("summarize", "tldr", "summarise"),
            ),
            ToolSpec(
                name="assistant.ask",
                description="Answer a question, chat, or reason about anything with the AI brain.",
                params={"prompt": "the question or request"},
                risk=Risk.SAFE,
                keywords=("ask ", "explain", "what is", "what are", "how do",
                          "how does", "why ", "tell me", "who is"),
                fallback=True,  # anything not matched by another tool becomes a chat
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        if not self.brain.can_think():
            return _NEEDS_MODEL
        if tool == "assistant.write":
            return await self.brain.generate(self._with_context(_arg(kwargs, "prompt")))
        if tool == "assistant.summarize":
            return await self.brain.summarize(_arg(kwargs, "text"))
        if tool == "assistant.ask":
            return await self.brain.reason(self._with_context(_arg(kwargs, "prompt")))
        raise ValueError(f"Unknown tool: {tool}")

    def _with_context(self, prompt: str) -> str:
        """Prepend relevant stored memories so answers reflect what ORIGAMI knows."""
        if self.memory is None:
            return prompt
        context = self.memory.context_for(prompt)
        if not context:
            return prompt
        return (f"Here is what you know about the user and their work:\n{context}\n\n"
                f"Using that context when relevant, respond to:\n{prompt}")


def _arg(kwargs: dict, key: str) -> str:
    return (kwargs.get(key) or "").strip()
