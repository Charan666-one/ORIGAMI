"""Passive auto-learning memory."""

from __future__ import annotations

from core.schemas.goal import Goal
from engines.memory.engine import JSONMemory
from engines.memory.learner import MemoryLearner, extract_facts
from main import build_orchestrator


def test_extracts_preferences_and_identity():
    facts = dict(extract_facts("I like jazz and my professor is Dr. Sharma"))
    assert "I like jazz" in facts
    assert facts["I like jazz"] is False              # preference -> ordinary
    assert any("professor" in f for f in facts)
    prof = next(f for f in facts if "professor" in f)
    assert facts[prof] is True                        # identity -> important


def test_ignores_plain_commands():
    assert extract_facts("play some lofi") == []
    assert extract_facts("remind me to run at 6am") == []
    assert extract_facts("open github.com") == []


def test_learner_stores_and_dedupes(tmp_path):
    mem = JSONMemory(path=tmp_path / "mem.json")
    learner = MemoryLearner(mem)

    learned = learner.learn("I work on CareerLens and I love AI")
    assert any("CareerLens" in f for f in learned)
    assert any("love ai" in f.lower() for f in learned)

    again = learner.learn("I love AI")            # already known
    assert again == []                             # deduped, nothing new


async def test_orchestrator_learns_from_requests(tmp_path):
    mem = JSONMemory(path=tmp_path / "mem.json")
    orch = build_orchestrator(memory=mem)
    result = await orch.handle(Goal(text="remember I prefer short formal emails"))
    # the request also carries a learnable preference
    assert any("prefer short formal emails" in f.lower() for f in mem_texts(mem))


def mem_texts(mem):
    return [r.text for r in mem.all()]
