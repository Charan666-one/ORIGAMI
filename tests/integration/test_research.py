"""Research skill — web search parsing, formatting, routing. Keyless (mocked)."""

from __future__ import annotations

from adapters.web.search import SearchResult, search
from core.schemas.goal import Goal
from main import build_orchestrator
from skills.research.skill import ResearchSkill

_FAKE_HTML = """
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fpython.org%2Fdocs">Python Docs</a>
<a class="result__snippet">Official Python documentation.</a>
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Freal-python.com">Real Python</a>
<a class="result__snippet">Tutorials for developers.</a>
"""


def test_search_parses_titles_urls_snippets():
    results = search("python", http_get=lambda q: _FAKE_HTML)
    assert results[0].title == "Python Docs"
    assert results[0].url == "https://python.org/docs"   # redirect unwrapped
    assert "Official" in results[0].snippet
    assert results[1].url == "https://real-python.com"


async def test_research_search_formats_results():
    def fake(query, max_results=5):
        return [SearchResult("Deadline Notice", "https://college.edu/notice", "Apply by Oct 1")]
    skill = ResearchSkill(searcher=fake)
    out = await skill.execute("research.search", query="exam deadline")
    assert "college.edu/notice" in out and "Deadline Notice" in out


async def test_research_answer_without_brain_shows_results():
    def fake(query, max_results=5):
        return [SearchResult("A", "https://a.com", "snippet a")]
    skill = ResearchSkill(brain=None, searcher=fake)
    out = await skill.execute("research.answer", query="anything")
    assert "a.com" in out


async def test_search_routes(tmp_path):
    orch = build_orchestrator()
    for text, expected in {
        "search for the latest AI news": "research.search",
        "look up python decorators": "research.search",
        "research quantum computing": "research.answer",
        "what's the latest on GATE 2026": "research.answer",
    }.items():
        plan = await orch.planner.plan(Goal(text=text))
        assert plan.steps[0].tool == expected, f"{text!r} -> {plan.steps[0].tool}"
