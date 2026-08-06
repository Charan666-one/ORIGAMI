"""ResearchSkill — web search + optional brain-synthesized answers.

`research.search` returns ranked results with URLs (prioritize official sources
yourself from the list). `research.answer` searches, then has the brain synthesize
a concise answer citing the sources. Keyless (DuckDuckGo). SAFE (read-only).
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill


class ResearchSkill(Skill):
    def __init__(self, brain: Any = None,
                 searcher: Optional[Callable[..., list]] = None) -> None:
        self.brain = brain
        self._searcher = searcher  # injectable for tests

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="research.answer",
                description="Search the web and give a concise answer with sources.",
                params={"query": "what to research"},
                risk=Risk.SAFE,
                keywords=("research ", "what's the latest", "whats the latest",
                          "latest on", "look up and summarize"),
            ),
            ToolSpec(
                name="research.search",
                description="Search the web and list the top results with links.",
                params={"query": "what to search for"},
                risk=Risk.SAFE,
                keywords=("search for", "search the web", "look up", "google ",
                          "find online", "web search"),
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        query = (kwargs.get("query") or "").strip()
        if not query:
            return "What should I search for?"
        try:
            results = self._search(query, max_results=5)
        except Exception as exc:
            return f"Search failed ({exc}). DuckDuckGo may be rate-limiting — try again."
        if not results:
            return f"No results for '{query}'."

        if tool == "research.search":
            return self._format(query, results)
        if tool == "research.answer":
            return await self._answer(query, results)
        raise ValueError(f"Unknown tool: {tool}")

    # ------------------------------------------------------------------ helpers

    def _search(self, query: str, max_results: int) -> list:
        if self._searcher is not None:
            return self._searcher(query, max_results=max_results)
        from adapters.web.search import search  # lazy
        return search(query, max_results=max_results)

    @staticmethod
    def _format(query: str, results: list) -> str:
        lines = [f"🔎 Top results for '{query}':"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.title}\n   {r.url}")
            if r.snippet:
                lines.append(f"   {r.snippet[:160]}")
        return "\n".join(lines)

    async def _answer(self, query: str, results: list) -> str:
        sources = "\n".join(f"[{i}] {r.title}: {r.snippet}" for i, r in enumerate(results, 1))
        links = "\n".join(f"[{i}] {r.url}" for i, r in enumerate(results, 1))
        if self.brain is None or not self.brain.can_think():
            return self._format(query, results)  # no model — just show results
        answer = await self.brain.summarize(
            f"Question: {query}\n\nSearch results:\n{sources}\n\n"
            f"Answer the question concisely using only these results.")
        return f"{answer}\n\nSources:\n{links}"
