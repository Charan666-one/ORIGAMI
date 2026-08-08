"""Web Intelligence — automatic freshness routing, sources, conflicts, offline.

Keyless: fake retriever, no network.
"""

from __future__ import annotations

import pytest

from engines.reasoning.llm import LLMEngine, LLMResponse, Task
from engines.web.freshness import Route, decide
from engines.web.intelligence import (Retriever, Source, WebIntelligence, WebState,
                                      authority_of)


# ===================================================== automatic freshness ====
# The point: no per-category rules. One question — could this have changed?

@pytest.mark.parametrize("q", [
    "what is python", "explain recursion", "what is the difference between a list and a tuple",
    "write a haiku about the sea", "define polymorphism", "teach me about pointers",
    "summarize this paragraph", "translate hello to french",
])
def test_stable_knowledge_stays_local(q):
    assert decide(q).route is Route.LOCAL, q


@pytest.mark.parametrize("q", [
    # technology / software
    "what is the latest python version", "current version of react",
    # news / world
    "what's happening in AI today", "latest news on the election",
    # sports
    "who won today's match", "current premier league standings",
    # finance
    "what is apple's current stock price", "bitcoin price now",
    # weather / travel
    "weather forecast for tomorrow", "cheapest flight to delhi this week",
    # commerce / local
    "is this restaurant open right now", "price of the macbook air",
    "is the m4 macbook available",
    # government / education
    "gate 2026 registration deadline", "latest upsc notification",
    # jobs
    "find me internships", "who is hiring ml engineers",
    # entertainment
    "trending movies this week", "recent releases on netflix",
])
def test_changing_information_goes_to_the_web(q):
    """Universal coverage — none of these have bespoke handlers."""
    assert decide(q).route is Route.FRESH, q


@pytest.mark.parametrize("q", [
    "what do you know about me", "my reminders", "my goals", "my codebases",
    "remind me to call mom at 5pm", "brain status", "health check", "my schedule",
])
def test_personal_data_never_leaves_the_machine(q):
    """ORIGAMI's own state must never become a search query."""
    assert decide(q).route is Route.LOCAL, q


def test_recent_year_implies_checking_reality():
    from datetime import datetime
    assert decide(f"python roadmap {datetime.now().year}").route is Route.FRESH


def test_decision_explains_itself():
    d = decide("latest python version")
    assert d.needs_web and "latest" in d.reason and d.confidence > 0.5


# ============================================================ source ranking ==

def test_official_sources_outrank_blogs():
    gov, _ = authority_of("https://gate2026.iitg.ac.in/dates.html")
    blog, _ = authority_of("https://someblog.com/gate-dates")
    assert gov > blog


def test_government_outranks_academic_outranks_web():
    g, _ = authority_of("https://india.gov.in/x")
    a, _ = authority_of("https://mit.edu/x")
    w, _ = authority_of("https://medium.com/x")
    assert g > a > w


def test_project_docs_count_as_primary():
    score, kind = authority_of("https://docs.python.org/3/whatsnew")
    assert kind == "primary" and score > 40


# =========================================================== the engine =======

class FakeRetriever(Retriever):
    name = "fake"

    def __init__(self, sources=None, online=True, pages=None):
        self._sources = sources or []
        self._online = online
        self._pages = pages or {}

    def is_online(self): return self._online
    def search(self, query, limit=5): return list(self._sources)
    def fetch(self, url): return self._pages.get(url, "")


class FakeBrain(LLMEngine):
    name = "fake"

    def can_think(self): return True

    async def complete(self, prompt, task=Task.REASON, **kwargs):
        assert "ONLY these sources" in prompt      # never free-invent
        return LLMResponse(text="Python 3.13 is the latest release.")


def _sources():
    return [
        Source("Python Downloads", "https://python.org/downloads", "Python 3.13 is current",
               authority=80, kind="primary"),
        Source("A Blog", "https://blog.example.com/py", "Python 3.11 is newest",
               authority=40),
    ]


async def test_answer_cites_sources_and_timestamp():
    web = WebIntelligence(retriever=FakeRetriever(_sources()), brain=FakeBrain())
    result = await web.answer("latest python version")
    rendered = result.render()
    assert "Python 3.13" in rendered
    assert "python.org/downloads" in rendered and "Sources (retrieved" in rendered
    assert web.state is WebState.IDLE


async def test_authority_orders_the_sources():
    web = WebIntelligence(retriever=FakeRetriever(_sources()), brain=FakeBrain())
    result = await web.answer("latest python version")
    assert result.sources[0].url.startswith("https://python.org")   # primary first


async def test_conflicting_figures_are_surfaced_not_hidden():
    conflicting = [
        Source("A", "https://a.com", "The population is 1400000000 people", authority=60),
        Source("B", "https://b.com", "The population is 1200000000 people", authority=60),
    ]
    web = WebIntelligence(retriever=FakeRetriever(conflicting), brain=FakeBrain())
    result = await web.answer("population")
    assert result.conflicts and "disagree" in result.render()


async def test_incidental_numbers_are_not_reported_as_conflicts():
    """Noise discipline: unrelated figures in snippets must not look like a clash."""
    noisy = [
        Source("A", "https://a.com", "Downloaded 761 times this week", authority=60),
        Source("B", "https://b.com", "See section 7 for details", authority=60),
    ]
    web = WebIntelligence(retriever=FakeRetriever(noisy), brain=FakeBrain())
    assert (await web.answer("something")).conflicts == []


async def test_near_identical_figures_are_not_a_conflict():
    close = [
        Source("A", "https://a.com", "About 1400000 users", authority=60),
        Source("B", "https://b.com", "Around 1405000 users", authority=60),
    ]
    web = WebIntelligence(retriever=FakeRetriever(close), brain=FakeBrain())
    assert (await web.answer("users")).conflicts == []


async def test_offline_says_so_and_never_invents():
    web = WebIntelligence(retriever=FakeRetriever(online=False), brain=FakeBrain())
    result = await web.answer("what is apple's stock price")
    assert result.offline and "offline" in result.answer.lower()
    assert not result.sources and web.state is WebState.OFFLINE


async def test_works_without_a_model():
    """No brain -> still returns real retrieved extracts, never a guess."""
    web = WebIntelligence(retriever=FakeRetriever(_sources()), brain=None)
    result = await web.answer("latest python version")
    assert "Python 3.13 is current" in result.render()


async def test_deep_mode_reads_pages():
    pages = {"https://python.org/downloads": "Full page text about Python 3.13 release"}
    web = WebIntelligence(retriever=FakeRetriever(_sources(), pages=pages), brain=FakeBrain())
    result = await web.answer("latest python version", deep=True)
    assert result.sources[0].text.startswith("Full page text")


async def test_status_exposes_dashboard_fields():
    web = WebIntelligence(retriever=FakeRetriever(_sources()), brain=FakeBrain())
    await web.answer("latest python version")
    s = web.status()
    for key in ("state", "query", "sources", "last_updated", "seconds", "confidence"):
        assert key in s


# ================================================= automatic, end to end ======

async def test_assistant_uses_the_web_without_being_asked():
    """The acceptance criterion: no "search the web" in the request."""
    from skills.assistant.skill import AssistantSkill
    web = WebIntelligence(retriever=FakeRetriever(_sources()), brain=FakeBrain())
    skill = AssistantSkill(brain=FakeBrain(), web=web)
    out = await skill.execute("assistant.ask", prompt="what is the latest python version")
    assert "Python 3.13" in out and "Sources" in out


async def test_assistant_stays_local_for_stable_questions():
    from skills.assistant.skill import AssistantSkill

    class LocalBrain(FakeBrain):
        async def reason(self, prompt, **kwargs):
            return "Recursion is a function calling itself."

    web = WebIntelligence(retriever=FakeRetriever([]), brain=FakeBrain())
    skill = AssistantSkill(brain=LocalBrain(), web=web)
    out = await skill.execute("assistant.ask", prompt="explain recursion")
    assert "function calling itself" in out
    assert web.state is WebState.IDLE          # the web was never touched


# ============================================ DON'T KNOW -> SEARCH ============

@pytest.mark.parametrize("reply", [
    "I don't know what that is.", "I'm not sure about that.",
    "I don't have information about XYZ.", "As of my last update, I cannot say.",
    "I'm not familiar with that topic.", "",
])
def test_hedging_answers_are_detected_as_uncertain(reply):
    from engines.web.freshness import is_uncertain
    assert is_uncertain(reply)


@pytest.mark.parametrize("reply", [
    "Recursion is a function that calls itself until a base case is reached.",
    "Paris is the capital of France.",
])
def test_confident_answers_are_not_escalated(reply):
    from engines.web.freshness import is_uncertain
    assert not is_uncertain(reply)


async def test_unknown_topic_escalates_to_the_web():
    """The model admits ignorance -> ORIGAMI searches instead of relaying it."""
    from skills.assistant.skill import AssistantSkill

    class IgnorantBrain(FakeBrain):
        async def reason(self, prompt, **kwargs):
            return "I don't have information about that."

    web = WebIntelligence(retriever=FakeRetriever(_sources()), brain=FakeBrain())
    skill = AssistantSkill(brain=IgnorantBrain(), web=web)
    out = await skill.execute("assistant.ask", prompt="what is zyxwv framework")
    assert "Sources" in out and "don't have information" not in out


async def test_offline_escalation_keeps_the_local_answer():
    """Offline: don't lose the local reply, and never fabricate a current one."""
    from skills.assistant.skill import AssistantSkill

    class IgnorantBrain(FakeBrain):
        async def reason(self, prompt, **kwargs):
            return "I'm not sure about that."

    web = WebIntelligence(retriever=FakeRetriever(online=False), brain=FakeBrain())
    skill = AssistantSkill(brain=IgnorantBrain(), web=web)
    out = await skill.execute("assistant.ask", prompt="what is zyxwv framework")
    assert "not sure" in out.lower()


async def test_search_failure_degrades_gracefully():
    class BrokenRetriever(FakeRetriever):
        def search(self, query, limit=5):
            raise RuntimeError("provider down")

    web = WebIntelligence(retriever=BrokenRetriever(), brain=FakeBrain())
    result = await web.answer("latest python version")
    assert "Search failed" in result.answer and web.state is WebState.IDLE


async def test_no_results_is_reported_not_invented():
    web = WebIntelligence(retriever=FakeRetriever([]), brain=FakeBrain())
    result = await web.answer("some obscure query")
    assert "found nothing" in result.answer.lower() and not result.sources
