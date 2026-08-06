"""Memory (C4) — store facts, retrieve by relevance, persist, and enrich the brain.

Keyless: uses a temp JSON file and a fake brain. No Ollama, no network.
"""

from __future__ import annotations

from core.schemas.goal import Goal
from engines.memory.engine import JSONMemory
from engines.reasoning.llm import LLMEngine, LLMResponse, Task
from main import build_orchestrator
from skills.memory.skill import MemorySkill


# ------------------------------------------------------------- the engine

def test_add_search_and_persist(tmp_path):
    path = tmp_path / "mem.json"
    m = JSONMemory(path=path)
    m.add("I am building ORIGAMI, a software AI operating system")
    m.add("I prefer short, concise emails")

    hits = m.search("tell me about origami")
    assert any("ORIGAMI" in r.text for r in hits)

    # a fresh instance reads the persisted file
    assert any("concise emails" in r.text for r in JSONMemory(path=path).all())


def test_search_ranks_by_relevance(tmp_path):
    m = JSONMemory(path=tmp_path / "mem.json")
    m.add("My dog is named Rex")
    m.add("My project ORIGAMI is a personal AI operating system")
    top = m.search("what is my project")[0]
    assert "ORIGAMI" in top.text


# ------------------------------------------------------------- the skill

async def test_remember_then_recall(tmp_path):
    skill = MemorySkill(memory=JSONMemory(path=tmp_path / "mem.json"))
    saved = await skill.execute("memory.remember", text="that I am building ORIGAMI")
    assert "ORIGAMI" in saved
    recalled = await skill.execute("memory.recall", query="origami")
    assert "ORIGAMI" in recalled


async def test_remember_routes_correctly(tmp_path):
    orch = build_orchestrator(memory=JSONMemory(path=tmp_path / "mem.json"))
    plan = await orch.planner.plan(Goal(text="remember that my exam is on Friday"))
    assert plan.steps[0].tool == "memory.remember"


# ------------------------------------------------- brain uses stored memory

class _EchoBrain(LLMEngine):
    """A brain that returns its prompt verbatim, so we can see injected context."""
    def can_think(self) -> bool:
        return True

    async def complete(self, prompt, task=Task.REASON, **kwargs) -> LLMResponse:
        return LLMResponse(text=prompt)

    async def reason(self, prompt, **kwargs) -> str:
        return prompt


async def test_assistant_answers_use_memory_context(tmp_path):
    from skills.assistant.skill import AssistantSkill
    mem = JSONMemory(path=tmp_path / "mem.json")
    mem.add("ORIGAMI is a software AI operating system I am building, not paper folding")

    skill = AssistantSkill(brain=_EchoBrain(), memory=mem)
    out = await skill.execute("assistant.ask", prompt="what is my origami project")

    assert "software AI operating system" in out   # memory was injected into the prompt
