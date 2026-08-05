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
            return self._search_and_play(kwargs.get("query", ""))
        if tool == "spotify.pause":
            return self._control(self.client.pause, "Paused")
        if tool == "spotify.next_track":
            return self._control(self.client.next_track, "Skipped to next track")
        if tool == "spotify.previous_track":
            return self._control(self.client.previous_track, "Back to previous track")
        raise ValueError(f"Unknown tool: {tool}")

    def _search_and_play(self, query: str) -> str:
        results = self.client.search(query, types=["track"], limit=1)
        items = results.get("tracks", {}).get("items", [])
        if not items:
            return f"Nothing found for '{query}'"
        track = items[0]
        self.client.play(uris=[track["uri"]])
        artists = ", ".join(a["name"] for a in track.get("artists", []))
        return f"Playing: {track['name']} — {artists}" if artists else f"Playing: {track['name']}"

    @staticmethod
    def _control(action, ok_message: str) -> str:
        """Run a playback control, translating Spotify's cryptic errors to plain text."""
        try:
            action()
            return ok_message
        except Exception as exc:
            msg = str(exc)
            if "Restriction violated" in msg:
                return "Spotify won't allow that right now (nothing to skip to in the current context)."
            if "No active device" in msg:
                return "No active Spotify device — open Spotify and play something first."
            raise
