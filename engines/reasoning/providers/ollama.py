"""OllamaProvider — local, free, offline reasoning via Ollama (localhost:11434).

Maps each Task to a preferred local model (the user's choice), with graceful
fallback if a model isn't pulled. Never requires an API key. If the Ollama server
isn't running, `is_available()` is False and the Brain Manager falls back.

Pull the models you want (only what you'll use):
    ollama pull qwen3:4b            # primary reasoning
    ollama pull qwen2.5-coder:3b    # coding
    ollama pull gemma3:1b           # fast, lightweight
    ollama pull phi4-mini           # low-resource fallback
"""

from __future__ import annotations

import os
from typing import Dict, List

import requests

from engines.reasoning.llm import LLMEngine, LLMResponse, Task

# Task -> ordered preference of local models (first one that's installed wins).
# Fast *instruct* models come first (snappy, clean output on 8GB); qwen3 (a
# reasoning model — slower, verbose) is a capable-but-heavier fallback.
DEFAULT_MODELS: Dict[Task, List[str]] = {
    Task.REASON: ["llama3.2:3b", "qwen2.5:3b", "gemma3:1b", "qwen3:4b", "phi4-mini"],
    Task.GENERATE: ["llama3.2:3b", "qwen2.5:3b", "gemma3:1b", "qwen3:4b", "phi4-mini"],
    Task.SUMMARIZE: ["llama3.2:3b", "gemma3:1b", "qwen2.5:3b", "qwen3:4b"],
    Task.CODE: ["qwen2.5-coder:3b", "qwen2.5:3b", "qwen3:4b"],
    Task.PLAN: ["llama3.2:3b", "qwen2.5:3b", "qwen3:4b"],
}

# Reasoning models emit long hidden "thinking" chains — very slow on 8GB. We turn
# that off so answers come back fast.
_THINKING_MODELS = ("qwen3", "deepseek-r1", "r1", "reasoning")


def _is_thinking_model(model: str) -> bool:
    m = model.lower()
    return any(t in m for t in _THINKING_MODELS)


class OllamaProvider(LLMEngine):
    name = "ollama"
    is_cloud = False

    def __init__(self, host: str | None = None, models: Dict[Task, List[str]] | None = None,
                 timeout: int = 120, keep_alive: str = "10m") -> None:
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.models = models or DEFAULT_MODELS
        self.timeout = timeout
        self.keep_alive = keep_alive  # keep the model warm in RAM between commands
        self._installed: List[str] | None = None

    def is_available(self) -> bool:
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def installed_models(self) -> List[str]:
        if self._installed is None:
            try:
                data = requests.get(f"{self.host}/api/tags", timeout=3).json()
                self._installed = [m["name"] for m in data.get("models", [])]
            except Exception:
                self._installed = []
        return self._installed

    def model_for(self, task: Task) -> str | None:
        """First preferred model for the task that is actually installed."""
        installed = self.installed_models()
        for preferred in self.models.get(task, []):
            # match "qwen3:4b" against installed "qwen3:4b" or "qwen3:4b-..."
            for got in installed:
                if got == preferred or got.startswith(preferred.split(":")[0] + ":"):
                    return got
        return installed[0] if installed else None

    async def complete(self, prompt: str, task: Task = Task.REASON, **kwargs) -> LLMResponse:
        model = kwargs.get("model") or self.model_for(task)
        if not model:
            raise RuntimeError("No Ollama model installed. Run e.g. `ollama pull llama3.2:3b`.")

        payload: dict = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "num_predict": kwargs.get("max_tokens", 800),  # cap length -> speed
                "temperature": kwargs.get("temperature", 0.7),
            },
        }
        if _is_thinking_model(model):
            payload["think"] = False  # skip slow hidden reasoning on 8GB

        resp = requests.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return LLMResponse(text=data.get("response", "").strip(), model=model, raw=data)
