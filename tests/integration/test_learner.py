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


# --------------------------------------------- trigger words must not be stripped

async def test_question_words_survive_routing():
    """Regression: the router stripped the matched keyword, so "why finish a
    project" reached the model as "finish a project" — a command, not a question.
    Every strange answer traced back to this."""
    orch = build_orchestrator()
    plan = await orch.planner.plan(Goal(text="in one sentence, why finish a project"))
    assert plan.steps[0].tool == "assistant.ask"
    assert plan.steps[0].args["prompt"] == "in one sentence, why finish a project"


async def test_write_requests_keep_their_verb():
    orch = build_orchestrator()
    plan = await orch.planner.plan(Goal(text="write a haiku about the sea"))
    assert plan.steps[0].args["prompt"] == "write a haiku about the sea"


async def test_non_semantic_keywords_are_still_stripped():
    """"play some lofi" -> query "some lofi": here the verb is not part of the value."""
    orch = build_orchestrator()
    plan = await orch.planner.plan(Goal(text="play some lofi"))
    assert plan.steps[0].args["query"] == "some lofi"
