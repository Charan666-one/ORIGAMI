"""Keyless web search via DuckDuckGo (no API key, no account).

Optimizations: robust per-result parsing, de-duplication by domain, official-source
ranking (.gov/.edu/.ac.in first), a retry on rate-limits, optional recency filter,
and a DuckDuckGo Instant Answer for direct factual queries. Brittle by nature
(HTML scrape) — callers should degrade gracefully. Injectable getters for tests.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from dataclasses import dataclass
from typing import Callable, List, Optional

_ENDPOINT = "https://html.duckduckgo.com/html/"
_IA_ENDPOINT = "https://api.duckduckgo.com/"
_TAGS = re.compile(r"<[^>]+>")
_OFFICIAL_TLDS = (".gov", ".gov.in", ".nic.in", ".edu", ".ac.in", ".edu.in")


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""

    @property
    def official(self) -> bool:
        return _is_official(self.url)


def _clean(s: str) -> str:
    return _TAGS.sub("", html.unescape(s)).strip()


def _domain(url: str) -> str:
    net = urllib.parse.urlparse(url).netloc.lower()
    return net[4:] if net.startswith("www.") else net


def _is_official(url: str) -> bool:
    d = _domain(url)
    return any(d.endswith(t) for t in _OFFICIAL_TLDS)


def _real_url(href: str) -> str:
    """DDG wraps results in a redirect (…/l/?uddg=<encoded>) — unwrap it."""
    if "uddg=" in href:
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
        if "uddg" in qs:
            return urllib.parse.unquote(qs["uddg"][0])
    if href.startswith("//"):
        return "https:" + href
    return href


def _parse(page: str) -> List[SearchResult]:
    """Per-result parsing keeps each title aligned with its own snippet."""
    results: List[SearchResult] = []
    for chunk in page.split('class="result__a"')[1:]:
        m_href = re.search(r'href="([^"]+)"', chunk)
        m_title = re.search(r">(.*?)</a>", chunk, re.DOTALL)
        m_snip = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', chunk, re.DOTALL)
        if not (m_href and m_title):
            continue
        url = _real_url(m_href.group(1))
        if url.startswith("http"):
            results.append(SearchResult(_clean(m_title.group(1)), url,
                                        _clean(m_snip.group(1)) if m_snip else ""))
    return results


def _dedupe(results: List[SearchResult]) -> List[SearchResult]:
    seen, out = set(), []
    for r in results:
        d = _domain(r.url)
        if d and d not in seen:
            seen.add(d)
            out.append(r)
    return out


def _rank(results: List[SearchResult], query: str) -> List[SearchResult]:
    """Combine DuckDuckGo's relevance order (position) + keyword match + a gentle
    official-source nudge. Relevance dominates so an irrelevant .gov never wins."""
    terms = {w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2}

    def key(item):
        i, r = item
        text = f"{r.title} {r.snippet} {r.url}".lower()
        relevance = sum(1 for t in terms if t in text)
        official = 0.75 if r.official else 0.0
        return i - relevance - official  # lower is better

    return [r for _, r in sorted(enumerate(results), key=key)]


def _default_get(query: str, recent: bool = False) -> str:
    import requests  # lazy
    data = {"q": query}
    if recent:
        data["df"] = "w"  # past week
    last_err = None
    for _ in range(2):  # small retry for transient rate-limits
        try:
            resp = requests.post(_ENDPOINT, data=data,
                                 headers={"User-Agent": "Mozilla/5.0",
                                          "Accept-Language": "en-US,en;q=0.9"},
                                 timeout=12)
            resp.raise_for_status()
            if "result__a" in resp.text:
                return resp.text
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    if last_err:
        raise last_err
    return ""


def search(query: str, max_results: int = 5, recent: bool = False,
           http_get: Optional[Callable[[str], str]] = None) -> List[SearchResult]:
    page = http_get(query) if http_get is not None else _default_get(query, recent=recent)
    return _rank(_dedupe(_parse(page)), query)[:max_results]


def instant_answer(query: str,
                   http_get_json: Optional[Callable[[str], dict]] = None) -> Optional[str]:
    """A direct answer for factual queries (definitions, facts), or None."""
    try:
        if http_get_json is not None:
            data = http_get_json(query)
        else:
            import requests  # lazy
            data = requests.get(_IA_ENDPOINT,
                                params={"q": query, "format": "json", "no_html": 1,
                                        "skip_disambig": 1},
                                headers={"User-Agent": "Mozilla/5.0"}, timeout=8).json()
        answer = (data.get("AbstractText") or data.get("Answer") or "").strip()
        return answer or None
    except Exception:
        return None
