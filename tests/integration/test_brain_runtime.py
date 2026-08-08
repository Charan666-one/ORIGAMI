"""Brain Runtime — lifecycle, model management, resources, recovery. No real Ollama."""

from __future__ import annotations

import pytest
import requests

from core.schemas.goal import Goal
from engines.reasoning.llm import Level, Task
from engines.reasoning.providers.ollama import OllamaProvider
from engines.reasoning.runtime import (BrainState, OllamaRuntime, model_size_gb)
from main import build_orchestrator


class FakeRuntime(OllamaRuntime):
    """Controllable runtime: no subprocess, no network."""

    def __init__(self, installed=True, healthy=True, models=("llama3.2:1b",),
                 starts_ok=True, free_gb=8.0):
        super().__init__(autostart=True)
        self._installed_flag, self._healthy = installed, healthy
        self._models, self._starts_ok, self._free = list(models), starts_ok, free_gb
        self.start_calls = 0

    def is_installed(self): return self._installed_flag
    def is_healthy(self, timeout=1.5): return self._healthy
    def models(self, refresh=False): return list(self._models)
    def loaded(self): return []

    def start(self):
        self.start_calls += 1
        if self._starts_ok:
            self._healthy = True
            self._started_by_us = True
            return True
        self.state = BrainState.ERROR
        self.last_error = "could not start"
        return False

    def can_load(self, model):
        need = model_size_gb(model)
        ok = self._free >= max(0.7, need * 0.55)
        return {"ok": ok, "need_gb": need, "free_gb": self._free,
                "reason": "" if ok else f"needs ~{need:.1f}GB, only {self._free:.1f}GB free"}


# ------------------------------------------------------------------ lifecycle

def test_already_running_needs_no_start():
    rt = FakeRuntime(healthy=True)
    assert rt.ensure() and rt.start_calls == 0


def test_not_running_starts_automatically():
    rt = FakeRuntime(healthy=False)
    assert rt.ensure()
    assert rt.start_calls == 1 and rt.state is BrainState.READY


def test_not_installed_is_reported_not_crashed():
    rt = FakeRuntime(installed=False, healthy=False)
    assert not rt.ensure()
    assert rt.state is BrainState.OFFLINE and "not installed" in rt.last_error


def test_autostart_can_be_disabled():
    rt = FakeRuntime(healthy=False)
    rt.autostart = False
    assert not rt.ensure() and rt.start_calls == 0


def test_stop_only_stops_what_origami_started():
    rt = FakeRuntime(healthy=False)
    rt.ensure()
    assert rt._started_by_us
    rt.stop()
    assert rt.state is BrainState.OFFLINE


# ------------------------------------------------------------------- recovery

def test_recovery_retries_then_gives_up():
    rt = FakeRuntime(healthy=False, starts_ok=False)
    assert not rt.recover(attempts=2)
    assert rt.state is BrainState.ERROR
    assert "temporarily unavailable" in rt.last_error


def test_recovery_succeeds_when_service_comes_back():
    rt = FakeRuntime(healthy=False, starts_ok=True)
    assert rt.recover() and rt.state is BrainState.READY


# ------------------------------------------------------------ model management

def test_model_presence():
    rt = FakeRuntime(models=("llama3.2:1b",))
    assert rt.has_model("llama3.2:1b") and rt.has_model("llama3.2:3b")  # same family
    assert not rt.has_model("qwen3:4b")


def test_missing_model_never_downloads_without_approval():
    rt = FakeRuntime(models=())
    result = rt.pull("llama3.2:1b")            # no approval given
    assert result["ok"] is False and result["needs_approval"]
    assert "Install llama3.2:1b" in result["message"]


def test_model_sizes_known_for_planning():
    assert model_size_gb("llama3.2:1b") < model_size_gb("qwen3:4b")


# ------------------------------------------------------------ resource safety

def test_plenty_of_memory_allows_load():
    assert FakeRuntime(free_gb=8.0).can_load("qwen3:4b")["ok"]


def test_memory_pressure_blocks_load():
    check = FakeRuntime(free_gb=0.4).can_load("qwen3:4b")
    assert not check["ok"] and "only 0.4GB free" in check["reason"]


def test_downgrades_to_a_smaller_installed_model():
    rt = FakeRuntime(models=("llama3.2:1b", "qwen3:4b"))
    assert rt.smaller_than("qwen3:4b") == "llama3.2:1b"
    assert rt.smaller_than("llama3.2:1b") is None


async def test_provider_downgrades_under_pressure(monkeypatch):
    rt = FakeRuntime(models=("llama3.2:1b", "qwen3:4b"), free_gb=1.2)
    p = OllamaProvider(runtime=rt)
    used = {}

    def fake_post(url, json=None, timeout=None):
        used["model"] = json["model"]
        class R:
            def raise_for_status(self): pass
            @staticmethod
            def json(): return {"response": "ok"}
        return R()
    monkeypatch.setattr(requests, "post", fake_post)

    await p.complete("hi", task=Task.REASON, level=Level.L2)
    assert used["model"] == "llama3.2:1b"      # picked the model that fits


async def test_resource_limited_when_nothing_fits(monkeypatch):
    rt = FakeRuntime(models=("qwen3:4b",), free_gb=0.2)
    p = OllamaProvider(runtime=rt)
    with pytest.raises(RuntimeError, match="Not enough memory"):
        await p.complete("hi", task=Task.REASON, level=Level.L2)
    assert rt.state is BrainState.RESOURCE_LIMITED


# ------------------------------------------------------------ provider states

async def test_unavailable_brain_gives_a_human_message():
    p = OllamaProvider(runtime=FakeRuntime(installed=False, healthy=False))
    with pytest.raises(RuntimeError, match="isn't installed"):
        await p.complete("hi")


async def test_no_model_asks_to_install():
    p = OllamaProvider(runtime=FakeRuntime(models=()))
    with pytest.raises(RuntimeError, match="install the brain"):
        await p.complete("hi")


async def test_timeout_is_bounded_and_reported(monkeypatch):
    p = OllamaProvider(runtime=FakeRuntime(), timeout=1)

    def boom(*a, **k):
        raise requests.exceptions.Timeout()
    monkeypatch.setattr(requests, "post", boom)
    with pytest.raises(RuntimeError, match="stopped waiting"):
        await p.complete("hi")


async def test_crash_midflight_recovers_and_retries(monkeypatch):
    rt = FakeRuntime()
    p = OllamaProvider(runtime=rt)
    calls = {"n": 0}

    def flaky(url, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.exceptions.ConnectionError()
        class R:
            def raise_for_status(self): pass
            @staticmethod
            def json(): return {"response": "recovered"}
        return R()
    monkeypatch.setattr(requests, "post", flaky)

    out = await p.complete("hi")
    assert out.text == "recovered" and calls["n"] == 2


async def test_records_latency_and_returns_to_ready(monkeypatch):
    rt = FakeRuntime()
    p = OllamaProvider(runtime=rt)

    def ok(url, json=None, timeout=None):
        class R:
            def raise_for_status(self): pass
            @staticmethod
            def json(): return {"response": "hello"}
        return R()
    monkeypatch.setattr(requests, "post", ok)

    await p.complete("hi")
    assert p.last_latency >= 0 and rt.state is BrainState.READY


# ------------------------------------------------------------------- surface

async def test_brain_skill_routing():
    orch = build_orchestrator()
    for text, tool in {"brain status": "brain.status",
                       "restart the brain": "brain.restart",
                       "install the brain": "brain.install"}.items():
        plan = await orch.planner.plan(Goal(text=text))
        assert plan.steps[0].tool == tool, f"{text!r} -> {plan.steps[0].tool}"


def test_non_ai_capabilities_survive_a_dead_brain():
    """A broken Brain must never take the whole app down."""
    from engines.reasoning.brain import BrainManager
    bm = BrainManager(providers=[OllamaProvider(
        runtime=FakeRuntime(installed=False, healthy=False))])
    assert not bm.can_think()               # honest about being offline
    assert bm.active_model() == "echo"      # and still usable
