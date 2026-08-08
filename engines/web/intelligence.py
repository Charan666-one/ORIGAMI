"""Web Intelligence — obtain current information, verify it, cite it.

    query → SEARCHING → READING → VERIFYING → REASONING → ANSWERING

The Brain reasons *over* what this returns; it is never the source of truth for
current facts. Retrieval is provider-independent (a `Retriever` contract), sources
are ranked by authority (official/primary first), conflicting figures are surfaced
rather than silently resolved, and every answer carries its sources and a
retrieval timestamp.

Offline is a first-class state: ORIGAMI says it cannot verify, and never invents.
"""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

MAX_PAGE_CHARS = 4000


class WebState(str, Enum):
    IDLE = "IDLE"
    SEARCHING = "SEARCHING"
    READING = "READING"
    VERIFYING = "VERIFYING"
    REASONING = "REASONING"
    ANSWERING = "ANSWERING"
    OFFLINE = "OFFLINE"


#: Source authority, highest first. Domain-shape based, not a hand-maintained
#: allow-list, so unknown official sources still rank correctly.
AUTHORITY = [
    (("gov", "gov.in", "nic.in", "gov.uk", "europa.eu"), 100, "government"),
    (("edu", "ac.in", "ac.uk", "edu.in"), 90, "academic"),
    (("who.int", "un.org", "nasa.gov", "nih.gov"), 95, "official body"),
    (("org",), 60, "organisation"),
]
#: Primary sources for their own subject (a project's own docs beat a blog).
PRIMARY_HINTS = ("docs.", "developer.", "official", "python.org", "github.com",
                 "gitlab.com", "apache.org", "mozilla.org", "w3.org")
_NUMBER = re.compile(r"\b\d+(?:[.,]\d+)*\b")
_TAGS = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)
_WS = re.compile(r"\s+")


@dataclass
class Source:
    title: str
    url: str
    snippet: str = ""
    text: str = ""
    authority: int = 40
    kind: str = "web"
    fetched_at: float = field(default_factory=time.time)

    @property
    def domain(self) -> str:
        from urllib.parse import urlparse
        net = urlparse(self.url).netloc.lower()
        return net[4:] if net.startswith("www.") else net

    def cite(self, index: int) -> str:
        return f"[{index}] {self.title[:70]} — {self.url}"


@dataclass
class WebAnswer:
    query: str
    answer: str
    sources: List[Source] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    offline: bool = False
    seconds: float = 0.0
    retrieved_at: float = field(default_factory=time.time)
    confidence: float = 0.0

    def render(self) -> str:
        if self.offline:
            return self.answer
        stamp = time.strftime("%d %b %Y, %H:%M", time.localtime(self.retrieved_at))
        out = [self.answer.strip()]
        if self.conflicts:
            out.append("\n⚠️  Sources disagree:")
            out.extend(f"   • {c}" for c in self.conflicts)
        if self.sources:
            out.append("\nSources (retrieved " + stamp + "):")
            out.extend("   " + s.cite(i) for i, s in enumerate(self.sources, 1))
        return "\n".join(out)


def authority_of(url: str) -> tuple:
    """(score, label) for a URL — official/primary sources rank highest."""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower()
    # government/academic/official bodies outrank everything
    for suffixes, score, label in AUTHORITY[:3]:
        if any(domain.endswith("." + s) or domain == s for s in suffixes):
            return score, label
    # a project's own docs/site are primary for their subject — checked before the
    # generic ".org" rule, or docs.python.org would score as a mere "organisation"
    if any(h in domain for h in PRIMARY_HINTS):
        return 80, "primary"
    for suffixes, score, label in AUTHORITY[3:]:
        if any(domain.endswith("." + s) or domain == s for s in suffixes):
            return score, label
    return 40, "web"


class Retriever(ABC):
    """Provider contract: search engines, APIs, RSS, a browser — all pluggable."""

    name = "base"

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> List[Source]: ...

    def fetch(self, url: str) -> str:
        return ""

    def is_online(self) -> bool:
        return True


class SearchRetriever(Retriever):
    """Default: the keyless search adapter + light page reading."""

    name = "search"

    def __init__(self, searcher: Optional[Callable] = None,
                 fetcher: Optional[Callable[[str], str]] = None) -> None:
        self._searcher = searcher
        self._fetcher = fetcher

    def is_online(self) -> bool:
        try:
            import requests
            requests.head("https://duckduckgo.com", timeout=3)
            return True
        except Exception:
            return False

    def search(self, query: str, limit: int = 5) -> List[Source]:
        if self._searcher is not None:
            results = self._searcher(query, max_results=limit)
        else:
            from adapters.web.search import search as ddg
            results = ddg(query, max_results=limit,
                          recent=any(w in query.lower()
                                     for w in ("latest", "today", "news", "current")))
        out = []
        for r in results:
            score, kind = authority_of(r.url)
            out.append(Source(title=r.title, url=r.url, snippet=r.snippet,
                              authority=score, kind=kind))
        return out

    def fetch(self, url: str) -> str:
        if self._fetcher is not None:
            return self._fetcher(url)
        try:
            import requests
            resp = requests.get(url, timeout=8, headers={
                "User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"})
            if resp.status_code != 200 or "html" not in resp.headers.get(
                    "content-type", "html"):
                return ""
            text = _TAGS.sub(" ", resp.text)
            import html as _html
            return _WS.sub(" ", _html.unescape(text)).strip()[:MAX_PAGE_CHARS]
        except Exception:
            return ""


class WebIntelligence:
    def __init__(self, retriever: Optional[Retriever] = None, brain=None,
                 on_state: Optional[Callable[[str, str], None]] = None) -> None:
        self.retriever = retriever or SearchRetriever()
        self.brain = brain
        self.on_state = on_state or (lambda s, d="": None)
        self.state = WebState.IDLE
        self.last: Optional[WebAnswer] = None

    def _set(self, state: WebState, detail: str = "") -> None:
        self.state = state
        try:
            self.on_state(state.value, detail)
        except Exception:
            pass

    # ------------------------------------------------------------------ ask

    async def answer(self, query: str, deep: bool = False, limit: int = 5) -> WebAnswer:
        started = time.perf_counter()

        if not self.retriever.is_online():
            self._set(WebState.OFFLINE)
            result = WebAnswer(query, offline=True, answer=(
                "I can't verify the current information because ORIGAMI is offline. "
                "I won't guess at something that may have changed."))
            self.last = result
            return result

        self._set(WebState.SEARCHING, query)
        try:
            sources = self.retriever.search(query, limit=limit)
        except Exception as exc:
            self._set(WebState.IDLE)
            return WebAnswer(query, answer=f"Search failed ({exc}). Try again shortly.")
        if not sources:
            self._set(WebState.IDLE)
            return WebAnswer(query, answer=f"I found nothing current for '{query}'.")

        # authority first, search relevance as the tie-break
        sources.sort(key=lambda s: -s.authority)

        if deep:                                   # read the top pages, not just snippets
            self._set(WebState.READING, sources[0].domain)
            for s in sources[:2]:
                s.text = self.retriever.fetch(s.url)

        self._set(WebState.VERIFYING)
        conflicts = self._conflicts(sources)

        self._set(WebState.REASONING)
        answer = await self._compose(query, sources, conflicts)

        self._set(WebState.ANSWERING)
        result = WebAnswer(query=query, answer=answer, sources=sources[:limit],
                           conflicts=conflicts, seconds=round(time.perf_counter() - started, 2),
                           confidence=min(1.0, sources[0].authority / 100))
        self.last = result
        self._set(WebState.IDLE)
        return result

    # ------------------------------------------------------------ verifying

    @staticmethod
    def _conflicts(sources: List[Source]) -> List[str]:
        """Surface genuine disagreement instead of silently picking a winner.

        Only *comparable* values are compared. An earlier version flagged any
        unmatched number, so incidental figures in a snippet ("761 downloads")
        looked like contradictions — noise that trains the user to ignore the
        warning. Values are grouped by shape, and only differing values of the
        same shape from different sources count.
        """
        shapes: Dict[str, Dict[str, str]] = {}   # shape -> {value: domain}
        for s in sources[:4]:
            for num in _NUMBER.findall(s.snippet or "")[:6]:
                shape = ("version" if re.fullmatch(r"\d+\.\d+(\.\d+)?", num)
                         else "large" if re.fullmatch(r"\d{4,}", num.replace(",", ""))
                         else None)
                if shape:
                    shapes.setdefault(shape, {}).setdefault(num, s.domain)

        out: List[str] = []
        for shape, values in shapes.items():
            if len(values) < 2:
                continue
            if shape == "large":     # only flag materially different magnitudes
                nums = sorted(float(v.replace(",", "")) for v in values)
                if nums[-1] and (nums[-1] - nums[0]) / nums[-1] < 0.02:
                    continue
            listed = ", ".join(f"{v} ({d})" for v, d in list(values.items())[:3])
            out.append(f"{shape} values differ: {listed}")
        return out[:2]

    # ------------------------------------------------------------ reasoning

    async def _compose(self, query: str, sources: List[Source],
                       conflicts: List[str]) -> str:
        """Summarise ONLY from retrieved material. No model -> return the extracts."""
        evidence = "\n".join(
            f"[{i}] {s.title} ({s.domain}, {s.kind}): {(s.text or s.snippet)[:600]}"
            for i, s in enumerate(sources[:4], 1))

        if self.brain is None or not self.brain.can_think():
            return "Here's what current sources say:\n" + "\n".join(
                f"   • {s.title}: {s.snippet[:150]}" for s in sources[:3])

        from engines.reasoning.llm import Task
        try:
            resp = await self.brain.complete(
                f"Question: {query}\n\nCurrent sources:\n{evidence}\n\n"
                f"Answer the question using ONLY these sources. Be specific and "
                f"concise. If the sources do not contain the answer, say so plainly. "
                f"Do not add facts that are not in the sources.",
                task=Task.SUMMARIZE, max_tokens=320)
            return resp.text.strip() or "The sources didn't clearly answer that."
        except Exception:
            return "Here's what current sources say:\n" + "\n".join(
                f"   • {s.title}: {s.snippet[:150]}" for s in sources[:3])

    # --------------------------------------------------------------- status

    def status(self) -> dict:
        last = self.last
        return {
            "state": self.state.value,
            "provider": self.retriever.name,
            "query": last.query if last else None,
            "sources": [{"title": s.title[:60], "url": s.url, "kind": s.kind}
                        for s in (last.sources if last else [])],
            "last_updated": last.retrieved_at if last else None,
            "seconds": last.seconds if last else None,
            "confidence": round(last.confidence, 2) if last else None,
            "offline": bool(last and last.offline),
        }
