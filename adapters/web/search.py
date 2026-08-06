"""Keyless web search via DuckDuckGo's HTML endpoint (no API key, no account).

Returns ranked organic results (title, url, snippet). Brittle by nature (HTML
scrape) — callers should degrade gracefully. `http_get` is injectable for tests.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from dataclasses import dataclass
from typing import Callable, List, Optional

_ENDPOINT = "https://html.duckduckgo.com/html/"
_RESULT = re.compile(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
_SNIPPET = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


def _clean(s: str) -> str:
    return _TAGS.sub("", html.unescape(s)).strip()


def _real_url(href: str) -> str:
    """DDG wraps results in a redirect (…/l/?uddg=<encoded>) — unwrap it."""
    if "uddg=" in href:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        if "uddg" in qs:
            return urllib.parse.unquote(qs["uddg"][0])
    return href if href.startswith("http") else "https:" + href


def _default_get(query: str) -> str:
    import requests  # lazy
    resp = requests.post(
        _ENDPOINT,
        data={"q": query},
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"},
        timeout=12,
    )
    resp.raise_for_status()
    return resp.text


def search(query: str, max_results: int = 5,
           http_get: Optional[Callable[[str], str]] = None) -> List[SearchResult]:
    page = (http_get or _default_get)(query)
    titles = _RESULT.findall(page)
    snippets = [_clean(s) for s in _SNIPPET.findall(page)]
    results: List[SearchResult] = []
    for i, (href, title) in enumerate(titles[:max_results]):
        results.append(SearchResult(
            title=_clean(title),
            url=_real_url(href),
            snippet=snippets[i] if i < len(snippets) else "",
        ))
    return results
