"""Project Health Engine — real analysis on synthetic repos + this repo."""

from __future__ import annotations

from pathlib import Path

from core.schemas.goal import Goal
from engines.health.analyzers import (analyze_architecture, analyze_capabilities,
                                      analyze_structure)
from engines.health.engine import ProjectHealthEngine
from engines.health.report import Finding, HealthReport, score_for
from main import build_orchestrator


def _repo(tmp_path: Path) -> Path:
    """A minimal ORIGAMI-shaped repo."""
    (tmp_path / "core").mkdir()
    (tmp_path / "skills" / "demo").mkdir(parents=True)
    (tmp_path / "engines" / "reasoning").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    (tmp_path / "main.py").write_text("from skills.demo.skill import DemoSkill\n", encoding="utf-8")
    (tmp_path / "core" / "planner.py").write_text('"""Planner."""\n', encoding="utf-8")
    (tmp_path / "skills" / "base.py").write_text('"""Base."""\n', encoding="utf-8")
    (tmp_path / "skills" / "registry.py").write_text('"""Registry."""\n', encoding="utf-8")
    (tmp_path / "engines" / "reasoning" / "llm.py").write_text('"""Brain."""\n', encoding="utf-8")
    (tmp_path / "skills" / "demo" / "skill.py").write_text(
        '"""Demo skill."""\n'
        "class DemoSkill:\n"
        "    def specs(self): return [ToolSpec()]\n"
        "    async def execute(self, tool, **kw): return 1\n", encoding="utf-8")
    (tmp_path / "tests" / "test_demo.py").write_text("# demo test\n", encoding="utf-8")
    return tmp_path


# ------------------------------------------------------- the architectural law

def test_detects_core_importing_a_capability(tmp_path):
    repo = _repo(tmp_path)
    (repo / "core" / "bad.py").write_text(
        '"""Bad."""\nfrom skills.demo.skill import DemoSkill\n', encoding="utf-8")
    findings = analyze_architecture(repo)
    assert any(f.severity == "critical" and "concrete capability" in f.message
               for f in findings)


def test_clean_core_has_no_architecture_criticals(tmp_path):
    findings = analyze_architecture(_repo(tmp_path))
    assert [f for f in findings if f.severity == "critical"] == []


def test_type_checking_imports_are_allowed(tmp_path):
    repo = _repo(tmp_path)
    (repo / "core" / "ok.py").write_text(
        '"""OK."""\nfrom typing import TYPE_CHECKING\n'
        "if TYPE_CHECKING:\n    from skills.demo.skill import DemoSkill\n", encoding="utf-8")
    assert [f for f in analyze_architecture(repo) if f.severity == "critical"] == []


# ------------------------------------------------------------- capability cards

def test_capability_card_scores_a_healthy_skill(tmp_path):
    caps, findings = analyze_capabilities(_repo(tmp_path))
    demo = next(c for c in caps if c.name == "demo")
    assert demo.contract_ok and demo.documented and demo.registered and demo.tested
    assert demo.score == 100.0


def test_empty_placeholder_is_info_not_critical(tmp_path):
    repo = _repo(tmp_path)
    (repo / "skills" / "stub").mkdir()
    (repo / "skills" / "stub" / "skill.py").write_text("", encoding="utf-8")
    caps, findings = analyze_capabilities(repo)
    assert "stub" not in [c.name for c in caps]           # dormant, not a capability
    assert any(f.severity == "info" and "placeholder" in f.message for f in findings)


def test_detects_stdlib_shadowing(tmp_path):
    """Regression: a top-level `platform/` package broke onnxruntime twice."""
    repo = _repo(tmp_path)
    (repo / "platform").mkdir()
    (repo / "platform" / "__init__.py").write_text("", encoding="utf-8")
    findings = analyze_structure(repo)
    assert any(f.severity == "critical" and "shadows the Python standard library" in f.message
               for f in findings)


def test_no_stdlib_shadowing_in_this_repo():
    from engines.health.engine import find_repo_root
    findings = analyze_structure(find_repo_root())
    assert not [f for f in findings if "shadows the Python standard library" in f.message]


def test_detects_large_file(tmp_path):
    repo = _repo(tmp_path)
    (repo / "core" / "big.py").write_text('"""Big."""\n' + "x = 1\n" * 500, encoding="utf-8")
    assert any("large file" in f.message for f in analyze_structure(repo))


# -------------------------------------------------------------------- scoring

def test_score_penalises_by_severity():
    findings = [Finding("architecture", "critical", "x"), Finding("architecture", "warning", "y")]
    assert score_for(findings, "architecture") == 69.0     # 100 - 25 - 6
    assert score_for(findings, "docs") == 100.0            # other categories untouched


def test_overall_is_the_mean_of_scores():
    r = HealthReport(scores={"a": 100.0, "b": 90.0})
    assert r.overall == 95.0


# ------------------------------------------------------- engine on THIS repo

def test_engine_runs_on_the_real_repo():
    report = ProjectHealthEngine().run()
    assert report.overall > 0
    assert report.scores["architecture"] == 100.0          # the law holds
    assert report.stats["capabilities"] >= 10


async def test_health_routing():
    orch = build_orchestrator()
    for text, expected in {
        "health check": "health.check",
        "project health": "health.check",
        "architecture audit": "health.audit",
        "capability health": "health.capabilities",
    }.items():
        plan = await orch.planner.plan(Goal(text=text))
        assert plan.steps[0].tool == expected, f"{text!r} -> {plan.steps[0].tool}"
