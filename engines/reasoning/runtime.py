"""Brain Runtime — owns the lifecycle of the local inference service.

ORIGAMI must never require the user to run `ollama serve`, load a model, or keep a
terminal open. This module makes the Brain a native part of ORIGAMI: it detects,
starts, health-checks, recovers and (when asked) installs the local runtime.

Architecturally this sits *below* the Brain interface — `OllamaProvider` owns a
runtime, so ORIGAMI itself stays provider-independent. A llama.cpp or other local
runtime implements the same `LocalRuntime` contract with no change above it.

Safety rules honoured here:
  • the service is bound to localhost only, never exposed publicly
  • models are NEVER downloaded without explicit user approval
  • RAM/CPU are checked before loading; the machine is never overloaded
  • failures degrade gracefully — non-AI capabilities keep working
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Dict, List, Optional

import requests


class BrainState(str, Enum):
    OFFLINE = "OFFLINE"                    # runtime not installed / unreachable
    STARTING = "STARTING"                  # service booting
    LOADING = "LOADING"                    # model being loaded into memory
    READY = "READY"                        # model available, idle
    THINKING = "THINKING"                  # inference in flight
    IDLE = "IDLE"                          # warm but unused
    RESOURCE_LIMITED = "RESOURCE_LIMITED"  # not enough RAM to load safely
    ERROR = "ERROR"                        # unrecoverable for now


#: approximate resident size (GB) per model — used for the RAM check
MODEL_SIZE_GB: Dict[str, float] = {
    "llama3.2:1b": 1.4, "gemma3:1b": 1.1, "qwen2.5:1.5b": 1.6,
    "llama3.2:3b": 2.4, "qwen2.5:3b": 2.3, "qwen2.5-coder:3b": 2.3,
    "phi4-mini": 2.6, "qwen3:4b": 3.0, "llama3.1:8b": 5.2,
}
DEFAULT_SIZE_GB = 2.5
#: Absolute floor below which loading anything is genuinely unsafe.
CRITICAL_FREE_GB = 0.7
#: macOS reports "available" conservatively — memory compression and cache eviction
#: reclaim more on demand, so a model runs comfortably with less free RAM than its
#: on-disk size. Measured on this machine: llama3.2:1b (1.4GB) serves fine with
#: ~1.5GB reported free. Requiring size+headroom would wrongly disable the Brain.
FIT_RATIO = 0.55


def model_size_gb(model: str) -> float:
    for known, size in MODEL_SIZE_GB.items():
        if model.startswith(known.split(":")[0]) and known.split(":")[-1] in model:
            return size
    return MODEL_SIZE_GB.get(model, DEFAULT_SIZE_GB)


class LocalRuntime(ABC):
    """Contract every local inference runtime implements (Ollama, llama.cpp, …)."""

    name = "base"

    @abstractmethod
    def is_installed(self) -> bool: ...

    @abstractmethod
    def is_healthy(self) -> bool: ...

    @abstractmethod
    def ensure(self, timeout: float = 20.0) -> bool:
        """Make the runtime usable, starting it if necessary."""

    @abstractmethod
    def models(self) -> List[str]: ...

    def install_hint(self) -> str:
        return ""


class OllamaRuntime(LocalRuntime):
    name = "ollama"

    def __init__(self, host: Optional[str] = None, autostart: Optional[bool] = None,
                 resources=None) -> None:
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.autostart = (os.getenv("ORIGAMI_AUTOSTART_BRAIN", "1") != "0"
                          if autostart is None else autostart)
        self.resources = resources
        self.state = BrainState.OFFLINE
        self.last_error = ""
        self._proc: Optional[subprocess.Popen] = None
        self._started_by_us = False
        self._failures = 0
        self._models_cache: Optional[List[str]] = None

    # ------------------------------------------------------------- detection

    def is_installed(self) -> bool:
        return shutil.which("ollama") is not None

    def install_hint(self) -> str:
        return "brew install ollama"

    def is_healthy(self, timeout: float = 1.5) -> bool:
        try:
            return requests.get(f"{self.host}/api/tags", timeout=timeout).status_code == 200
        except Exception:
            return False

    # --------------------------------------------------------------- startup

    def start(self) -> bool:
        """Launch the service detached — no terminal window, survives this process."""
        if not self.is_installed():
            self.state = BrainState.OFFLINE
            self.last_error = "ollama is not installed"
            return False
        if self.is_healthy():
            return True
        try:
            self.state = BrainState.STARTING
            self._proc = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,      # detached: no terminal, no job control
            )
            self._started_by_us = True
            return True
        except Exception as exc:
            self.state = BrainState.ERROR
            self.last_error = f"could not start ollama: {exc}"
            return False

    def ensure(self, timeout: float = 20.0) -> bool:
        """Idempotent: returns True once the local API is answering."""
        if self.is_healthy():
            self.state = BrainState.READY if self.state in (
                BrainState.OFFLINE, BrainState.STARTING) else self.state
            self._failures = 0
            return True

        if not self.autostart:
            self.state = BrainState.OFFLINE
            self.last_error = "autostart disabled (ORIGAMI_AUTOSTART_BRAIN=0)"
            return False
        if not self.is_installed():
            self.state = BrainState.OFFLINE
            self.last_error = "ollama is not installed"
            return False
        if not self.start():
            return False

        deadline = time.time() + timeout
        while time.time() < deadline:               # wait for health
            if self.is_healthy():
                self.state = BrainState.READY
                self._models_cache = None
                self._failures = 0
                return True
            time.sleep(0.4)

        self.state = BrainState.ERROR
        self.last_error = f"ollama did not become healthy within {timeout:.0f}s"
        return False

    def recover(self, attempts: int = 2) -> bool:
        """Restart after a crash, with a hard cap so we never loop forever."""
        for _ in range(attempts):
            self._failures += 1
            self._proc = None
            if self.ensure(timeout=15.0):
                return True
            time.sleep(1.0)
        self.state = BrainState.ERROR
        self.last_error = "brain is temporarily unavailable"
        return False

    def stop(self) -> None:
        """Only ever stops a service ORIGAMI itself started."""
        if self._proc and self._started_by_us and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None
        self._started_by_us = False
        self.state = BrainState.OFFLINE

    # ---------------------------------------------------------------- models

    def models(self, refresh: bool = False) -> List[str]:
        if self._models_cache is not None and not refresh:
            return self._models_cache
        try:
            data = requests.get(f"{self.host}/api/tags", timeout=3).json()
            self._models_cache = [m["name"] for m in data.get("models", [])]
        except Exception:
            self._models_cache = []
        return self._models_cache

    def has_model(self, model: str) -> bool:
        base = model.split(":")[0]
        return any(m == model or m.startswith(base + ":") for m in self.models())

    def pull(self, model: str, approved: bool = False,
             on_progress: Optional[Callable[[str], None]] = None) -> Dict[str, object]:
        """Download a model. Requires explicit approval — never automatic."""
        if not approved:
            return {"ok": False, "needs_approval": True, "model": model,
                    "size_gb": model_size_gb(model),
                    "message": (f"ORIGAMI Brain is not installed. Install {model} "
                                f"(~{model_size_gb(model):.1f}GB)?")}
        if not self.ensure():
            return {"ok": False, "error": self.last_error}
        self.state = BrainState.LOADING
        try:
            proc = subprocess.run(["ollama", "pull", model], capture_output=True,
                                  text=True, timeout=1800)
            ok = proc.returncode == 0
            self._models_cache = None
            self.state = BrainState.READY if ok else BrainState.ERROR
            if on_progress:
                on_progress(proc.stdout or proc.stderr)
            return {"ok": ok, "model": model,
                    "error": "" if ok else (proc.stderr or "pull failed").strip()[:200]}
        except Exception as exc:
            self.state = BrainState.ERROR
            return {"ok": False, "error": str(exc)}

    def unload(self, model: str) -> bool:
        """Free RAM by evicting a loaded model (keep_alive=0)."""
        try:
            requests.post(f"{self.host}/api/generate",
                          json={"model": model, "prompt": "", "keep_alive": 0},
                          timeout=10)
            return True
        except Exception:
            return False

    def loaded(self) -> List[Dict[str, object]]:
        """Models currently resident in memory."""
        try:
            data = requests.get(f"{self.host}/api/ps", timeout=3).json()
            return [{"name": m.get("name"),
                     "size_gb": round(m.get("size", 0) / 1_073_741_824, 2)}
                    for m in data.get("models", [])]
        except Exception:
            return []

    # ------------------------------------------------------- resource safety

    def can_load(self, model: str) -> Dict[str, object]:
        """Is there enough RAM to load this model without hurting the machine?"""
        need = model_size_gb(model)
        free = None
        if self.resources is not None:
            snap = self.resources.snapshot()
            free = getattr(snap, "ram_available_gb", None)
        if free is None:
            try:
                import psutil
                free = psutil.virtual_memory().available / 1_073_741_824
            except Exception:
                return {"ok": True, "reason": "memory unknown", "need_gb": need}

        # already resident? then it costs nothing more
        if any(str(m["name"]).startswith(model.split(":")[0]) for m in self.loaded()):
            return {"ok": True, "reason": "already loaded", "need_gb": 0.0,
                    "free_gb": round(free, 2)}

        ok = free >= max(CRITICAL_FREE_GB, need * FIT_RATIO)
        return {"ok": ok, "need_gb": need, "free_gb": round(free, 2),
                "reason": "" if ok else
                          f"needs ~{need:.1f}GB, only {free:.1f}GB free"}

    def smaller_than(self, model: str) -> Optional[str]:
        """The largest installed model that is smaller than `model` — the
        graceful downgrade when RAM is tight."""
        target = model_size_gb(model)
        options = [(model_size_gb(m), m) for m in self.models()]
        smaller = sorted((s, m) for s, m in options if s < target)
        return smaller[-1][1] if smaller else None

    # ---------------------------------------------------------------- status

    def status(self) -> Dict[str, object]:
        healthy = self.is_healthy()
        # reconcile: a fresh handle starts OFFLINE, but the service may already be
        # up (e.g. another ORIGAMI surface started it) — report what is true now.
        if healthy and self.state in (BrainState.OFFLINE, BrainState.STARTING):
            self.state = BrainState.IDLE if self.loaded() else BrainState.READY
        elif not healthy and self.state in (BrainState.READY, BrainState.IDLE,
                                            BrainState.THINKING):
            self.state = BrainState.OFFLINE
        return {
            "runtime": self.name,
            "installed": self.is_installed(),
            "healthy": healthy,
            "state": self.state.value,
            "host": self.host,
            "models": self.models(),
            "loaded": self.loaded(),
            "autostart": self.autostart,
            "managed_by_origami": self._started_by_us,
            "failures": self._failures,
            "error": self.last_error,
            "install_hint": self.install_hint(),
        }
