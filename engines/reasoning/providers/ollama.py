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
import time
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

    def __init__(self, host: str | None = None, timeout: int | None = None,
                 keep_alive: str = "10m", runtime=None, resources=None) -> None:
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        # hard cap per call so a hung/thrashing model can never wait forever
        self.timeout = timeout or int(os.getenv("ORIGAMI_LLM_TIMEOUT", "60"))
        self.keep_alive = keep_alive  # keep the model warm in RAM between commands
        self._installed: List[str] | None = None
        self.last_latency = 0.0
        if runtime is None:
            from engines.reasoning.runtime import OllamaRuntime
            runtime = OllamaRuntime(host=self.host, resources=resources)
        #: owns start/health/recovery so the user never runs `ollama serve`
        self.runtime = runtime

    def is_available(self) -> bool:
        """Available if the service is reachable — starting it if it isn't."""
        return self.runtime.ensure()

    def installed_models(self) -> List[str]:
        if self._installed is None:
            self._installed = self.runtime.models(refresh=True)
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
        from engines.reasoning.runtime import BrainState

        level = kwargs.get("level", Level.L2)
        # 1. make sure the brain is actually up (starts it if it isn't)
        if not self.runtime.ensure():
            raise RuntimeError(self._unavailable_message())

        model = kwargs.get("model") or self.model_for(task, level)
        if not model:
            raise RuntimeError('ORIGAMI Brain has no model installed. '
                               'Approve one with: origami "install the brain"')

        # 2. resource safety — downgrade rather than overload the machine
        check = self.runtime.can_load(model)
        if not check["ok"]:
            smaller = self.runtime.smaller_than(model)
            if smaller:
                model = smaller
            else:
                self.runtime.state = BrainState.RESOURCE_LIMITED
                raise RuntimeError(f"Not enough memory for the Brain ({check['reason']}). "
                                   f"Close some apps or install a smaller model.")

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

        self.runtime.state = BrainState.THINKING
        started = time.perf_counter()
        try:
            # (connect, read): fail fast if the server is down; cap total read time
            resp = requests.post(f"{self.host}/api/generate", json=payload,
                                 timeout=(5, self.timeout))
            resp.raise_for_status()
        except requests.exceptions.Timeout as exc:
            self.runtime.state = BrainState.READY
            raise RuntimeError(
                f"The local model took over {self.timeout}s — stopped waiting. Try a "
                f"shorter request, a smaller/faster model, or raise ORIGAMI_LLM_TIMEOUT."
            ) from exc
        except requests.exceptions.RequestException as exc:
            # 3. the service died mid-flight — recover once, then retry
            if self.runtime.recover():
                resp = requests.post(f"{self.host}/api/generate", json=payload,
                                     timeout=(5, self.timeout))
                resp.raise_for_status()
            else:
                self.runtime.state = BrainState.ERROR
                raise RuntimeError("ORIGAMI Brain is temporarily unavailable.") from exc

        data = resp.json()
        self.last_latency = round(time.perf_counter() - started, 2)
        self.runtime.state = BrainState.READY
        return LLMResponse(text=data.get("response", "").strip(), model=model, raw=data)

    def _unavailable_message(self) -> str:
        if not self.runtime.is_installed():
            return ("ORIGAMI Brain isn't installed. Install the local runtime with "
                    f"`{self.runtime.install_hint()}` — then I'll handle the rest.")
        return "ORIGAMI Brain is temporarily unavailable."
