"""EchoEngine — the keyless, offline, zero-model fallback.

It does no reasoning: it cannot actually think or write, so `can_think = False`.
It exists so the whole pipeline runs with no model installed (routing via keyword
matching still works). Real generation needs a local model (Ollama) or cloud.
"""

from __future__ import annotations

from engines.reasoning.llm import LLMEngine, LLMResponse, Task


class EchoEngine(LLMEngine):
    name = "echo"

    def can_think(self) -> bool:
        return False

    async def complete(self, prompt: str, task: Task = Task.REASON, **kwargs) -> LLMResponse:
        return LLMResponse(text=prompt, model="echo")

    async def generate(self, instruction: str, **kwargs) -> str:
        # honest: no model to compose with — echo the instruction back unchanged
        return instruction.strip()
