"""Freshness decision — "does answering this accurately need the real world *now*?"

Deliberately general. There are no per-topic rules (no "sports handler", no
"stock handler"): the question is only whether the answer could have changed
since the model was trained. That is what makes coverage universal — a category
nobody anticipated still routes correctly.

    decide("what is recursion")            -> LOCAL   (stable knowledge)
    decide("latest python version")        -> FRESH   (versions change)
    decide("who won today's match")        -> FRESH   (temporal)
    decide("what did I tell you about X")  -> LOCAL   (personal memory)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Route(str, Enum):
    LOCAL = "local"      # the brain/memory can answer reliably
    FRESH = "fresh"      # needs current information from the world


@dataclass
class Decision:
    route: Route
    reason: str
    confidence: float = 0.8

    @property
    def needs_web(self) -> bool:
        return self.route is Route.FRESH


# --- explicit "right now" markers ------------------------------------------
_TEMPORAL = (
    "latest", "current", "currently", "today", "tonight", "now", "right now",
    "recent", "recently", "this week", "this month", "this year", "these days",
    "up to date", "up-to-date", "newest", "just released", "so far",
    "at the moment", "nowadays", "still ",
)
# --- things that are values/states of the world, which drift ----------------
_VOLATILE = (
    "price", "cost", "how much", "worth", "rate", "stock", "shares", "market",
    "score", "won", "winner", "result", "standings", "fixture", "match",
    "weather", "forecast", "temperature", "rain",
    "status", "available", "availability", "in stock", "open now", "opening hours",
    "deadline", "last date", "schedule", "timetable", "release date",
    "version", "release", "update", "changelog", "news", "headline",
    "who is the", "population of", "ceo of", "president of", "prime minister",
    "vacancy", "vacancies", "hiring", "internship", "job opening", "apply",
    "flight", "hotel", "ticket", "showtimes", "trending",
)
# --- stable knowledge: explanation, reasoning, creation ---------------------
_STABLE = (
    "what is", "what are", "explain", "how does", "how do i", "why does", "why is",
    "define", "definition", "difference between", "meaning of", "example of",
    "write ", "draft ", "summarize", "translate", "calculate", "convert",
    "teach me", "help me understand", "walk me through",
)
# --- ORIGAMI's own data: never the web -------------------------------------
_PERSONAL = (
    "my reminder", "my goal", "my memory", "my codebase", "my project",
    "what do you know about me", "my streak", "my brief", "my calendar",
    "remind me", "remember", "my profile", "who am i", "my repos",
    "my repositories", "brain status", "health check", "voice status",
    "auth status", "my schedule",
)
_YEAR = re.compile(r"\b20[2-9]\d\b")


def decide(text: str, now_year: Optional[int] = None) -> Decision:
    """Route a request. Personal data wins, then explicit freshness, then stability."""
    t = (text or "").lower().strip()
    if not t:
        return Decision(Route.LOCAL, "empty request", 1.0)

    # 1. ORIGAMI's own state is always local — never leaks to a search engine
    if any(p in t for p in _PERSONAL):
        return Decision(Route.LOCAL, "about your own data", 0.95)

    # 2. explicit temporal markers are decisive
    for marker in _TEMPORAL:
        if marker in t:
            return Decision(Route.FRESH, f"asks for {marker.strip()} information", 0.95)

    # 3. values/states that drift in the real world
    for marker in _VOLATILE:
        if marker in t:
            return Decision(Route.FRESH, f"'{marker.strip()}' changes over time", 0.85)

    # 4. a recent year implies checking reality rather than recalling it
    if now_year is None:
        from datetime import datetime
        now_year = datetime.now().year
    years = [int(y) for y in _YEAR.findall(t)]
    if any(y >= now_year - 1 for y in years):
        return Decision(Route.FRESH, "refers to a recent year", 0.8)

    # 5. stable knowledge: explanation, creation, reasoning
    if any(t.startswith(s) or f" {s}" in t for s in _STABLE):
        return Decision(Route.LOCAL, "stable knowledge or generation", 0.85)

    # 6. Default local: cheaper, private, and wrong less often than searching
    #    every idle remark. Explicit markers above catch the real cases, and
    #    `is_uncertain()` escalates afterwards if the local answer admits it
    #    doesn't know — so "unknown topic" still reaches the web.
    return Decision(Route.LOCAL, "no indication the answer changes", 0.6)


#: Phrases a model uses when it does not actually know. Their presence means the
#: local answer is worthless, so the request should be retried against the web
#: rather than handed to the user as-is.
_HEDGES = (
    "i don't know", "i do not know", "i'm not sure", "i am not sure",
    "i don't have information", "i do not have information",
    "i don't have access", "i do not have access", "no information about",
    "i'm not familiar", "i am not familiar", "i cannot provide information",
    "i can't provide information", "as of my last update", "my training data",
    "my knowledge cutoff", "i'm unable to find", "not aware of",
    "there is no information", "i couldn't find any information",
)


def is_uncertain(answer: str) -> bool:
    """Did the local answer effectively admit ignorance?

    This is the "DON'T KNOW → SEARCH" rule: rather than trying to predict what the
    model knows, ask it first and escalate when its own reply hedges.
    """
    if not answer or len(answer.strip()) < 12:
        return True
    low = answer.lower()
    return any(h in low for h in _HEDGES)
