"""Code understanding — scan, persist per-codebase learning, explain, ask, route."""

from __future__ import annotations

from core.schemas.goal import Goal
from engines.knowledge.codebases import CodebaseStore
from engines.knowledge.scanner import scan_codebase
from engines.reasoning.llm import LLMEngine, LLMResponse, Task
from main import build_orchestrator
from skills.code.skill import CodeSkill


class FakeBrain(LLMEngine):
    def can_think(self):
        return True

    async def complete(self, prompt, task=Task.REASON, **kwargs):
        # the code skill uses complete() for both explain and ask
        return LLMResponse(text="A FastAPI + React app with a backend and frontend.")


def _sample_repo(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / "backend" / "app.py").write_text("print('hi')", encoding="utf-8")
    (tmp_path / "README.md").write_text("# MyApp\nDoes things.", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name":"myapp"}', encoding="utf-8")
    return tmp_path


def test_scanner_extracts_structure(tmp_path):
    prof = scan_codebase(str(_sample_repo(tmp_path)))
    assert "Python" in prof["languages"]
    assert "backend" in prof["structure"] and "frontend" in prof["structure"]
    assert "README.md" in prof["key_files"]


async def test_scan_learns_and_persists(tmp_path):
    repo = _sample_repo(tmp_path / "MyApp")
    store = CodebaseStore(path=tmp_path / "cb.json")
    skill = CodeSkill(brain=FakeBrain(), store=store)

    msg = await skill.execute("code.scan", text=str(repo))
    assert "Scanned MyApp" in msg and "FastAPI" in msg

    # a fresh store reads the persisted learning
    reloaded = CodebaseStore(path=tmp_path / "cb.json")
    assert reloaded.get("MyApp")["summary"].startswith("A FastAPI")


async def test_explain_and_ask_use_stored_knowledge(tmp_path):
    store = CodebaseStore(path=tmp_path / "cb.json")
    store.save("MyApp", {"summary": "A FastAPI + React app.", "path": "/x"})
    skill = CodeSkill(brain=FakeBrain(), store=store)

    explained = await skill.execute("code.explain", _raw="explain the codebase MyApp")
    assert "FastAPI" in explained
    asked = await skill.execute("code.ask", _raw="ask about MyApp: what backend")
    assert "FastAPI" in asked


async def test_scan_routes():
    orch = build_orchestrator()
    for text, expected in {
        "scan careerlens": "code.scan",
        "my codebases": "code.list",
        "explain the codebase ORIGAMI": "code.explain",
    }.items():
        plan = await orch.planner.plan(Goal(text=text))
        assert plan.steps[0].tool == expected, f"{text!r} -> {plan.steps[0].tool}"
