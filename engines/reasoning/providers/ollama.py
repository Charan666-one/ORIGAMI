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
from typing import List

import requests

from engines.reasoning.llm import Level, LLMEngine, LLMResponse, Task

# Model tiers by intelligence level (first installed wins). Smallest/fastest for
# L1; heavier reasoning for L2; a coder for CODE. All degrade to whatever is
# installed, so a single model (e.g. llama3.2:3b) serves every tier.
FAST_MODELS = ["llama3.2:1b", "gemma3:1b", "qwen2.5:1.5b", "llama3.2:3b", "phi4-mini"]
STANDARD_MODELS = ["qwen2.5:3b", "llama3.2:3b", "qwen3:4b", "gemma3:1b", "llama3.2:1b"]
CODE_MODELS = ["qwen2.5-coder:3b", "qwen2.5:3b", "qwen3:4b", "llama3.2:3b"]

# Reasoning models emit long hidden "thinking" chains — very slow on 8GB. We turn
# that off so answers come back fast.
_THINKING_MODELS = ("qwen3", "deepseek-r1", "r1", "reasoning")


def _is_thinking_model(model: str) -> bool:
    m = model.lower()
    return any(t in m for t in _THINKING_MODELS)


class OllamaProvider(LLMEngine):
    name = "ollama"
    is_cloud = False

    def __init__(self, host: str | None = None, timeout: int = 120,
                 keep_alive: str = "10m") -> None:
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
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

    def model_for(self, task: Task, level: Level = Level.L2) -> str | None:
        """First installed model in the tier for this task/level (smallest that fits)."""
        if task is Task.CODE:
            prefs = CODE_MODELS
        elif level is Level.L1:
            prefs = FAST_MODELS
        else:
            prefs = STANDARD_MODELS
        installed = self.installed_models()
        for preferred in prefs:
            for got in installed:  # match "qwen3:4b" or "qwen3:4b-..."
                if got == preferred or got.startswith(preferred.split(":")[0] + ":"):
                    return got
        return installed[0] if installed else None

    async def complete(self, prompt: str, task: Task = Task.REASON, **kwargs) -> LLMResponse:
        level = kwargs.get("level", Level.L2)
        model = kwargs.get("model") or self.model_for(task, level)
        if not model:
            raise RuntimeError("No Ollama model installed. Run e.g. `ollama pull llama3.2:3b`.")

        # shorter cap for fast/simple asks -> snappier; more room for standard work
        default_tokens = 256 if level is Level.L1 else 700
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {
                "num_predict": kwargs.get("max_tokens", default_tokens),
                "temperature": kwargs.get("temperature", 0.7),
                # smaller context window = less RAM + faster on an 8GB machine
                "num_ctx": kwargs.get("num_ctx", 2048),
            },
        }
        if _is_thinking_model(model):
            payload["think"] = False  # skip slow hidden reasoning on 8GB

        resp = requests.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return LLMResponse(text=data.get("response", "").strip(), model=model, raw=data)
