"""Brain Manager — selection rules, offline-first, cloud consent, resources.

All keyless: uses fake providers, never touches Ollama or a network.
"""

from __future__ import annotations

from engines.reasoning.brain import BrainManager
from engines.reasoning.llm import LLMEngine, LLMResponse, Task
from engines.reasoning.resources import ResourceMonitor


class FakeProvider(LLMEngine):
    def __init__(self, name="fake", available=True, cloud=False):
        self.name = name
        self._available = available
        self.is_cloud = cloud

    def is_available(self) -> bool:
        return self._available

    async def complete(self, prompt, task=Task.REASON, **kwargs) -> LLMResponse:
        return LLMResponse(text=f"FAKE({self.name}):{prompt[:12]}", model=self.name)


# ------------------------------------------------------- offline-first selection

def test_falls_back_to_echo_when_no_provider_available():
    bm = BrainManager(providers=[FakeProvider(available=False)])
    assert not bm.can_think()
    assert bm.select(Task.REASON).name == "echo"


def test_uses_first_available_local_provider():
    good = FakeProvider(name="local")
    bm = BrainManager(providers=[FakeProvider(available=False), good])
    assert bm.can_think()
    assert bm.select(Task.REASON) is good


async def test_generate_delegates_to_provider():
    bm = BrainManager(providers=[FakeProvider(name="local")])
    out = await bm.generate("write a poem")
    assert "FAKE(local)" in out


# ------------------------------------------------------------- cloud is consented

def test_cloud_skipped_without_consent():
    cloud = FakeProvider(name="cloud", cloud=True)
    bm = BrainManager(providers=[cloud])  # no consent hook
    assert bm.select(Task.REASON).name == "echo"   # cloud NOT used


def test_cloud_used_only_with_consent():
    cloud = FakeProvider(name="cloud", cloud=True)
    bm = BrainManager(providers=[cloud], cloud_consent=lambda name, task: True)
    assert bm.select(Task.REASON) is cloud


def test_local_preferred_over_cloud_even_with_consent():
    local = FakeProvider(name="local")
    cloud = FakeProvider(name="cloud", cloud=True)
    bm = BrainManager(providers=[local, cloud], cloud_consent=lambda n, t: True)
    assert bm.select(Task.REASON) is local   # offline-first


# ------------------------------------------------------------- resource monitor

def test_resource_monitor_snapshot_has_fields():
    snap = ResourceMonitor().snapshot()
    for field in ("ram_available_gb", "cpu_percent", "battery_percent", "temperature_c"):
        assert hasattr(snap, field)


def test_resource_monitor_is_low_returns_bool():
    assert isinstance(ResourceMonitor().is_low(), bool)
