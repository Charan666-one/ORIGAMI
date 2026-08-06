"""Brain Manager — level classification, minimum-intelligence routing, cloud
consent, resource awareness. All keyless (fake providers, no Ollama, no network).
"""

from __future__ import annotations

from engines.reasoning.brain import BrainManager
from engines.reasoning.llm import Level, LLMEngine, LLMResponse, Task, classify_level
from engines.reasoning.resources import ResourceMonitor


class FakeProvider(LLMEngine):
    def __init__(self, name="fake", available=True, cloud=False):
        self.name = name
        self._available = available
        self.is_cloud = cloud

    def is_available(self) -> bool:
        return self._available

    async def complete(self, prompt, task=Task.REASON, **kwargs) -> LLMResponse:
        return LLMResponse(text=f"FAKE({self.name})", model=self.name)


class LowResources(ResourceMonitor):
    def is_low(self) -> bool:
        return True


class NormalResources(ResourceMonitor):
    def is_low(self) -> bool:
        return False


# ------------------------------------------------------------ level classifier

def test_classify_short_simple_is_fast():
    assert classify_level(Task.REASON, "what is 2 plus 2") is Level.L1


def test_classify_essay_is_standard():
    assert classify_level(Task.GENERATE, "write an essay about the ocean") is Level.L2


def test_classify_code_is_standard():
    assert classify_level(Task.CODE, "reverse a string") is Level.L2


def test_classify_in_depth_is_advanced():
    assert classify_level(Task.REASON, "give me an in depth analysis of X") is Level.L3


# ------------------------------------------------------------ offline-first

def test_falls_back_to_echo_when_no_local():
    bm = BrainManager(providers=[FakeProvider(available=False)])
    assert not bm.can_think()
    provider, _ = bm.decide(Task.REASON, "hi")
    assert provider.name == "echo"


def test_simple_ask_uses_local_at_L1():
    local = FakeProvider(name="local")
    bm = BrainManager(providers=[local])
    provider, level = bm.decide(Task.REASON, "quick: say hi")
    assert provider is local and level is Level.L1


# ------------------------------------------------------------ cloud is consented

def test_cloud_not_used_for_simple_even_if_available():
    cloud = FakeProvider(name="cloud", cloud=True)
    bm = BrainManager(providers=[cloud], cloud_consent=lambda n, t: True)
    provider, _ = bm.decide(Task.REASON, "say hi")   # L1 -> never cloud
    assert provider.name == "echo"                    # no local, cloud not for L1


def test_cloud_used_for_advanced_with_consent():
    local = FakeProvider(name="local")
    cloud = FakeProvider(name="cloud", cloud=True)
    bm = BrainManager(providers=[local, cloud], cloud_consent=lambda n, t: True,
                      resources=NormalResources())
    provider, level = bm.decide(Task.REASON, "give an in depth analysis of quantum computing")
    assert provider is cloud and level is Level.L3


def test_advanced_without_consent_falls_back_to_local():
    local = FakeProvider(name="local")
    cloud = FakeProvider(name="cloud", cloud=True)
    bm = BrainManager(providers=[local, cloud], resources=NormalResources())  # no consent
    provider, level = bm.decide(Task.REASON, "in depth research on X")
    assert provider is local and level is Level.L2   # downgraded to best local


# ------------------------------------------------------------ resource-aware

def test_low_resources_downgrade_to_fast():
    local = FakeProvider(name="local")
    bm = BrainManager(providers=[local], resources=LowResources())
    _, level = bm.decide(Task.GENERATE, "write a long detailed essay about the sea")
    assert level is Level.L1   # would be L2, but low RAM -> fast tier


# ------------------------------------------------------------ delegation + resources

async def test_generate_delegates_to_provider():
    bm = BrainManager(providers=[FakeProvider(name="local")])
    out = await bm.generate("write a poem")
    assert "FAKE(local)" in out


async def test_system_context_injected_into_reasoning():
    seen = {}

    class Capture(LLMEngine):
        name = "cap"

        async def complete(self, prompt, task=Task.REASON, **kwargs) -> LLMResponse:
            seen["prompt"] = prompt
            return LLMResponse(text="ok")

    bm = BrainManager(providers=[Capture()], resources=NormalResources(),
                      system_context="THE USER IS CHARAN, a CS student.")
    await bm.reason("what should I focus on")
    assert "CHARAN" in seen["prompt"]
    assert "what should I focus on" in seen["prompt"]


def test_resource_monitor_snapshot_has_fields():
    snap = ResourceMonitor().snapshot()
    for field in ("ram_available_gb", "cpu_percent", "battery_percent", "temperature_c"):
        assert hasattr(snap, field)
