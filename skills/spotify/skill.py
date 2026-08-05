"""SpotifySkill — wraps the existing adapters/spotify/client.py (never reimplements).

Proves the engine end-to-end. Playback tools are SAFE (no consequence to others).
The client is created lazily so building the orchestrator never requires Spotify
credentials — only actually *calling* a tool touches the network.
"""

from __future__ import annotations

from typing import Any, List

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill


class SpotifySkill(Skill):
    def __init__(self, client: Any = None) -> None:
        self._client = client  # injected fake in tests; real client built lazily

    @property
    def client(self):
        if self._client is None:
            from adapters.spotify.client import SpotifyClient  # lazy import
            self._client = SpotifyClient()
        return self._client

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(
                name="spotify.search_and_play",
                description="Search Spotify and play the top result.",
                params={"query": "what to search for and play"},
                risk=Risk.SAFE,
                keywords=("play", "listen to", "put on"),
            ),
            ToolSpec(
                name="spotify.pause",
                description="Pause playback.",
                risk=Risk.SAFE,
                keywords=("pause", "stop the music", "stop music"),
            ),
            ToolSpec(
                name="spotify.next_track",
                description="Skip to the next track.",
                risk=Risk.SAFE,
                keywords=("next track", "skip", "next song"),
            ),
            ToolSpec(
                name="spotify.previous_track",
                description="Go to the previous track.",
                risk=Risk.SAFE,
                keywords=("previous track", "previous song", "go back a song"),
            ),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        if tool == "spotify.search_and_play":
            query = kwargs.get("query", "")
            played = self.client.search_and_play(query)
            return f"Playing: {played}" if played else f"Nothing found for '{query}'"
        if tool == "spotify.pause":
            self.client.pause()
            return "Paused"
        if tool == "spotify.next_track":
            self.client.next_track()
            return "Skipped to next track"
        if tool == "spotify.previous_track":
            self.client.previous_track()
            return "Back to previous track"
        raise ValueError(f"Unknown tool: {tool}")
