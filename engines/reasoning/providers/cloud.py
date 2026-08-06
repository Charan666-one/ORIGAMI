"""CloudProvider — OPTIONAL cloud reasoning, never a dependency.

One OpenAI-compatible client covers Groq / OpenAI / others (base URL + key). It is
only `is_available()` when its API key env var is set, and the Brain Manager will
only ever route to it after an explicit user consent callback — ORIGAMI never
automatically depends on a paid/cloud API (offline-first).

Configured off env, e.g. Groq (free tier):
    ORIGAMI_CLOUD=groq
    GROQ_API_KEY=...
"""

from __future__ import annotations

import os
from typing import Optional

import requests

from engines.reasoning.llm import LLMEngine, LLMResponse, Task

# name -> (base_url, default_model, api_key_env)
PRESETS = {
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", "GROQ_API_KEY"),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini", "OPENAI_API_KEY"),
}


class CloudProvider(LLMEngine):
    is_cloud = True

    def __init__(self, preset: str = "groq", model: Optional[str] = None,
                 timeout: int = 60) -> None:
        base_url, default_model, key_env = PRESETS.get(preset, PRESETS["groq"])
        self.name = f"cloud:{preset}"
        self.base_url = base_url
        self.model = model or default_model
        self.api_key = os.getenv(key_env, "")
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(self.api_key)

    async def complete(self, prompt: str, task: Task = Task.REASON, **kwargs) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError(f"{self.name} has no API key set.")
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}]},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return LLMResponse(text=text, model=self.model, raw=data)
