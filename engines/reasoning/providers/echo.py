"""EchoEngine — the default, keyless, offline brain.

It does no reasoning: `complete()` echoes, and `plan()` inherits the base
keyword matcher. This is enough for command-style goals ("play some lofi") and
lets the whole pipeline run in CI with no API key and no model install.
"""

from __future__ import annotations

from engines.reasoning.llm import LLMEngine, LLMResponse


class EchoEngine(LLMEngine):
    name = "echo"

    async def complete(self, prompt: str, **kwargs) -> LLMResponse:
        return LLMResponse(text=prompt)
