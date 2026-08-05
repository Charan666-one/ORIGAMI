"""SpotifySkill — wraps the existing adapters/spotify/client.py (never reimplements).

Playback tools are SAFE (no consequence to others). The client is created lazily
so building the orchestrator never requires credentials.

"Just play it" behaviour: if no Spotify device is active, the skill launches the
Spotify desktop app, waits for it to register as a Connect device, and targets it
directly — so the user never has to pre-open Spotify.
"""

from __future__ import annotations

import subprocess
import sys
import time
from typing import Any, List, Optional

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
                description="Open Spotify if needed, then search and play the top result.",
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

    # ------------------------------------------------------------------ helpers

    def _search_and_play(self, query: str) -> str:
        results = self.client.search(query, types=["track"], limit=1)
        items = results.get("tracks", {}).get("items", [])
        if not items:
            return f"Nothing found for '{query}'"
        track = items[0]

        device_id = self._ensure_device()
        if device_id is None:
            return ("Couldn't reach a Spotify device — open the Spotify app and "
                    "try again (it may still be starting up).")

        self.client.play(uris=[track["uri"]], device_id=device_id)
        artists = ", ".join(a["name"] for a in track.get("artists", []))
        return f"Playing: {track['name']} — {artists}" if artists else f"Playing: {track['name']}"

    def _ensure_device(self, wait_seconds: float = 15.0) -> Optional[str]:
        """Return a Spotify device id to play on, launching the app if none exist.

        Prefers an already-active device; otherwise the first available one. If no
        devices are registered, opens the Spotify desktop app and polls until one
        appears (or the timeout elapses)."""
        devices = self.client.list_devices()
        if not devices:
            self._launch_spotify_app()
            deadline = time.time() + wait_seconds
            while time.time() < deadline and not devices:
                time.sleep(1.5)
                devices = self.client.list_devices()
        if not devices:
            return None
        active = next((d for d in devices if d.get("is_active")), None)
        return (active or devices[0]).get("id")

    @staticmethod
    def _launch_spotify_app() -> None:
        """Open the Spotify desktop app (SAFE). macOS today; extend per-OS later."""
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", "-a", "Spotify"], check=False)
            elif sys.platform.startswith("win"):
                subprocess.run(["cmd", "/c", "start", "spotify:"], check=False)
            else:  # linux
                subprocess.run(["spotify"], check=False)
        except Exception:
            pass  # best-effort; _ensure_device handles the no-device case

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
                return "No active Spotify device — try 'play <song>' first to wake it up."
            raise
