"""YouTubeSkill — search YouTube and open the top result, keyless (no API key).

It fetches YouTube's public search-results HTML, extracts the first videoId, and
opens the watch page in the default browser (which autoplays). If extraction
fails (YouTube markup changed / no results), it falls back to opening the search
page. SAFE — opening a video has no consequence to others.

`opener` and `http_get` are injectable so tests never hit the network or a browser.
"""

from __future__ import annotations

import re
import subprocess
import sys
import urllib.parse
from typing import Any, Callable, List, Optional

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill

_VIDEO_ID = re.compile(r'"videoId":"([\w-]{11})"')


class YouTubeSkill(Skill):
    def __init__(self, opener: Optional[Callable[[str], None]] = None,
                 http_get: Optional[Callable[[str], str]] = None) -> None:
        self._opener = opener
        self._http_get = http_get

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="youtube.play",
                description="Search YouTube and open the top video in the browser.",
                params={"query": "what to watch"},
                risk=Risk.SAFE,
                keywords=("youtube", "watch ", "yt "),
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        if tool == "youtube.play":
            return self._play((kwargs.get("query") or "").strip())
        raise ValueError(f"Unknown tool: {tool}")

    # ------------------------------------------------------------------ helpers

    def _play(self, query: str) -> str:
        if not query:
            return "What should I search on YouTube?"
        search_url = ("https://www.youtube.com/results?search_query="
                      + urllib.parse.quote(query))
        video_id = self._first_video_id(search_url)
        if video_id:
            url = f"https://www.youtube.com/watch?v={video_id}"
            self._open(url)
            return f"Playing on YouTube: {query}"
        self._open(search_url)
        return f"Opened YouTube search for: {query} (couldn't auto-pick a video)"

    def _first_video_id(self, search_url: str) -> Optional[str]:
        try:
            html = self._get(search_url)
            match = _VIDEO_ID.search(html)
            return match.group(1) if match else None
        except Exception:
            return None

    def _get(self, url: str) -> str:
        if self._http_get is not None:
            return self._http_get(url)
        import requests  # lazy
        resp = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"},
            timeout=10,
        )
        return resp.text

    def _open(self, url: str) -> None:
        if self._opener is not None:
            self._opener(url)
            return
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", url], check=False)
            elif sys.platform.startswith("win"):
                subprocess.run(["cmd", "/c", "start", "", url], check=False)
            else:
                subprocess.run(["xdg-open", url], check=False)
        except Exception:
            pass
