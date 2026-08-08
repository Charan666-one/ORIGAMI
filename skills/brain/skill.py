"""BrainSkill — inspect and manage ORIGAMI's Brain without touching Ollama.

The user should never need to know the runtime exists. These tools exist for when
something goes wrong, or to approve a model download (never automatic).
"""

from __future__ import annotations

from typing import Any, List, Optional

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill

RECOMMENDED = "llama3.2:1b"


class BrainSkill(Skill):
    def __init__(self, brain: Any = None) -> None:
        self.brain = brain

    def _runtime(self):
        for p in getattr(self.brain, "providers", []) or []:
            if hasattr(p, "runtime"):
                return p, p.runtime
        from engines.reasoning.providers.ollama import OllamaProvider
        p = OllamaProvider()
        return p, p.runtime

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(name="brain.status",
                     description="Brain state: runtime, model, memory, latency.",
                     risk=Risk.SAFE,
                     keywords=("brain status", "is the brain ready", "brain state",
                               "which model", "what model are you using", "llm status")),
            ToolSpec(name="brain.install",
                     description="Download a local model (asks first — never automatic).",
                     params={"text": "model name (optional)"}, risk=Risk.CONFIRM,
                     keywords=("install the brain", "install a model", "download the model",
                               "download a model", "pull a model", "set up the brain")),
            ToolSpec(name="brain.restart", description="Restart the local Brain runtime.",
                     risk=Risk.SAFE,
                     keywords=("restart the brain", "restart brain", "brain restart",
                               "fix the brain", "brain is stuck")),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        provider, runtime = self._runtime()
        if tool == "brain.status":
            return self._status(provider, runtime)
        if tool == "brain.restart":
            runtime.stop()
            ok = runtime.ensure()
            return ("🧠 Brain restarted and ready." if ok
                    else f"Couldn't restart: {runtime.last_error}")
        if tool == "brain.install":
            return self._install(runtime, (kwargs.get("text") or "").strip())
        raise ValueError(f"Unknown tool: {tool}")

    def _install(self, runtime, requested: str) -> str:
        model = requested.split()[-1] if requested and "/" not in requested else ""
        model = model if model and ":" in model else RECOMMENDED
        if runtime.has_model(model):
            return f"✅ {model} is already installed."
        # CONFIRM risk means the executor already asked the user — approve the pull
        result = runtime.pull(model, approved=True)
        if result.get("ok"):
            return f"✅ Installed {model}. The Brain is ready — just ask me something."
        return f"Install failed: {result.get('error') or result.get('message')}"

    def _status(self, provider, runtime) -> str:
        s = runtime.status()
        loaded = ", ".join(f"{m['name']} ({m['size_gb']}GB)" for m in s["loaded"]) or "none"
        lines = [
            f"🧠 ORIGAMI BRAIN — {s['state']}",
            f"   Runtime : {s['runtime']} {'✅ healthy' if s['healthy'] else '○ not running'}"
            f"{'  (started by ORIGAMI)' if s['managed_by_origami'] else ''}",
            f"   Models  : {', '.join(s['models']) or 'none installed'}",
            f"   Loaded  : {loaded}",
        ]
        if getattr(provider, "last_latency", 0):
            lines.append(f"   Latency : {provider.last_latency}s (last inference)")
        check = runtime.can_load(RECOMMENDED)
        if check.get("free_gb") is not None:
            lines.append(f"   Memory  : {check['free_gb']}GB free"
                         f"{'' if check['ok'] else ' ⚠️ ' + str(check['reason'])}")
        if not s["installed"]:
            lines.append(f"   → install the runtime: {s['install_hint']}")
        elif not s["models"]:
            lines.append('   → install a model: origami "install the brain"')
        if s["error"]:
            lines.append(f"   ⚠️  {s['error']}")
        lines.append("   You never need to run the server yourself — ORIGAMI starts it.")
        return "\n".join(lines)
