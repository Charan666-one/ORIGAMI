"""
adapters/spotify/client.py
Spotify Web API client — playback control, search, playlists, library.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests

from adapters.spotify.auth import SpotifyAuth

logger = logging.getLogger(__name__)

SPOTIFY_API_BASE = "https://api.spotify.com/v1"


class SpotifyClientError(Exception):
    """Raised on Spotify API failures."""


class SpotifyClient:
    """
    High-level Spotify Web API client for ORIGAMI.

    Usage:
        client = SpotifyClient()
        client.play()
        results = client.search("lofi hip hop", types=["track"])
    """

    def __init__(self, auth: Optional[SpotifyAuth] = None, timeout: int = 10) -> None:
        self._auth = auth or SpotifyAuth()
        self._timeout = timeout
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        resp = self._session.get(
            f"{SPOTIFY_API_BASE}{path}",
            headers=self._auth.get_headers(),
            params=params,
            timeout=self._timeout,
        )
        self._raise_for_status(resp)
        return self._json(resp)

    def _post(self, path: str, body: Optional[dict] = None) -> Any:
        resp = self._session.post(
            f"{SPOTIFY_API_BASE}{path}",
            headers=self._auth.get_headers(),
            json=body,
            timeout=self._timeout,
        )
        self._raise_for_status(resp)
        return self._json(resp)

    def _put(self, path: str, body: Optional[dict] = None, params: Optional[dict] = None) -> Any:
        resp = self._session.put(
            f"{SPOTIFY_API_BASE}{path}",
            headers=self._auth.get_headers(),
            json=body,
            params=params,
            timeout=self._timeout,
        )
        self._raise_for_status(resp)
        return self._json(resp)

    def _delete(self, path: str, body: Optional[dict] = None) -> None:
        resp = self._session.delete(
            f"{SPOTIFY_API_BASE}{path}",
            headers=self._auth.get_headers(),
            json=body,
            timeout=self._timeout,
        )
        self._raise_for_status(resp)

    @staticmethod
    def _json(resp: requests.Response) -> Any:
        """Parse a JSON body, tolerating empty/no-content responses (204, player
        commands) that would otherwise crash json.loads with 'Expecting value'."""
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {}

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        if not resp.ok:
            try:
                message = resp.json().get("error", {}).get("message", resp.text)
            except Exception:
                message = resp.text
            raise SpotifyClientError(f"Spotify API {resp.status_code}: {message}")

    # ------------------------------------------------------------------
    # Player — Playback Control
    # ------------------------------------------------------------------

    def get_playback_state(self) -> dict[str, Any]:
        """Return current playback state (device, track, progress, etc.)."""
        return self._get("/me/player")

    def get_current_track(self) -> Optional[dict[str, Any]]:
        """Return info about the currently playing track, or None."""
        data = self._get("/me/player/currently-playing")
        return data.get("item") if data else None

    def play(
        self,
        device_id: Optional[str] = None,
        context_uri: Optional[str] = None,
        uris: Optional[list[str]] = None,
        offset: Optional[dict] = None,
        position_ms: int = 0,
    ) -> None:
        """
        Start or resume playback.

        Args:
            device_id: Spotify device ID to target (None = active device).
            context_uri: Spotify context URI (album, playlist, artist).
            uris: List of Spotify track URIs to play.
            offset: Offset object for where to start in context.
            position_ms: Position to start playback at.
        """
        body: dict[str, Any] = {}
        if context_uri:
            body["context_uri"] = context_uri
        if uris:
            body["uris"] = uris
        if offset:
            body["offset"] = offset
        if position_ms:
            body["position_ms"] = position_ms

        params = {"device_id": device_id} if device_id else None
        self._put("/me/player/play", body=body, params=params)
        logger.info("Spotify playback started.")

    def pause(self, device_id: Optional[str] = None) -> None:
        """Pause playback."""
        params = {"device_id": device_id} if device_id else None
        self._put("/me/player/pause", params=params)
        logger.info("Spotify playback paused.")

    def next_track(self, device_id: Optional[str] = None) -> None:
        """Skip to the next track."""
        params = {"device_id": device_id} if device_id else None
        self._post("/me/player/next")
        logger.info("Skipped to next track.")

    def previous_track(self, device_id: Optional[str] = None) -> None:
        """Skip to the previous track."""
        self._post("/me/player/previous")
        logger.info("Skipped to previous track.")

    def set_volume(self, volume_percent: int, device_id: Optional[str] = None) -> None:
        """
        Set playback volume.

        Args:
            volume_percent: Volume level 0-100.
        """
        volume_percent = max(0, min(100, volume_percent))
        params: dict[str, Any] = {"volume_percent": volume_percent}
        if device_id:
            params["device_id"] = device_id
        self._put("/me/player/volume", params=params)
        logger.info("Set volume to %d%%.", volume_percent)

    def seek(self, position_ms: int, device_id: Optional[str] = None) -> None:
        """Seek to a position in the current track."""
        params: dict[str, Any] = {"position_ms": position_ms}
        if device_id:
            params["device_id"] = device_id
        self._put("/me/player/seek", params=params)

    def set_shuffle(self, state: bool) -> None:
        """Enable or disable shuffle."""
        self._put("/me/player/shuffle", params={"state": str(state).lower()})

    def set_repeat(self, mode: str = "off") -> None:
        """
        Set repeat mode.

        Args:
            mode: 'off', 'track', or 'context'.
        """
        assert mode in ("off", "track", "context"), "mode must be off/track/context"
        self._put("/me/player/repeat", params={"state": mode})

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------

    def list_devices(self) -> list[dict[str, Any]]:
        """List all available Spotify Connect devices."""
        result = self._get("/me/player/devices")
        return result.get("devices", [])

    def transfer_playback(self, device_id: str, play: bool = True) -> None:
        """Transfer playback to a different device."""
        self._put("/me/player", body={"device_ids": [device_id], "play": play})
        logger.info("Transferred playback to device %s.", device_id)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        types: Optional[list[str]] = None,
        limit: int = 10,
        market: str = "IN",
    ) -> dict[str, Any]:
        """
        Search Spotify catalog.

        Args:
            query: Search query string.
            types: List of types: 'track', 'album', 'artist', 'playlist'.
            limit: Number of results per type.
            market: ISO 3166-1 alpha-2 country code.
        """
        if types is None:
            types = ["track"]
        return self._get(
            "/search",
            params={
                "q": query,
                "type": ",".join(types),
                "limit": limit,
                "market": market,
            },
        )

    def search_and_play(self, query: str, track_type: str = "track") -> Optional[str]:
        """
        Search for a query and immediately play the top result.

        Returns the URI of the played item, or None if not found.
        """
        results = self.search(query, types=[track_type], limit=1)
        items = results.get(f"{track_type}s", {}).get("items", [])
        if not items:
            logger.warning("No results found for query: %s", query)
            return None
        uri = items[0]["uri"]
        self.play(uris=[uri] if track_type == "track" else None,
                  context_uri=uri if track_type != "track" else None)
        logger.info("Playing '%s' (uri=%s).", items[0].get("name", "?"), uri)
        return uri

    # ------------------------------------------------------------------
    # Playlists
    # ------------------------------------------------------------------

    def list_playlists(self, limit: int = 20) -> list[dict[str, Any]]:
        """List current user's playlists."""
        result = self._get("/me/playlists", params={"limit": limit})
        return result.get("items", [])

    def get_playlist(self, playlist_id: str) -> dict[str, Any]:
        """Get full playlist details."""
        return self._get(f"/playlists/{playlist_id}")

    def create_playlist(
        self,
        user_id: str,
        name: str,
        description: str = "",
        public: bool = False,
    ) -> dict[str, Any]:
        """Create a new playlist."""
        result = self._post(
            f"/users/{user_id}/playlists",
            {"name": name, "description": description, "public": public},
        )
        logger.info("Created playlist '%s'.", name)
        return result

    def add_tracks_to_playlist(self, playlist_id: str, track_uris: list[str]) -> None:
        """Add tracks to a playlist."""
        self._post(f"/playlists/{playlist_id}/tracks", {"uris": track_uris})
        logger.info("Added %d tracks to playlist %s.", len(track_uris), playlist_id)

    # ------------------------------------------------------------------
    # User Library
    # ------------------------------------------------------------------

    def get_liked_songs(self, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        """Get user's liked songs."""
        result = self._get("/me/tracks", params={"limit": limit, "offset": offset})
        return result.get("items", [])

    def save_tracks(self, track_ids: list[str]) -> None:
        """Add tracks to the user's library."""
        self._put("/me/tracks", body={"ids": track_ids})

    def remove_tracks(self, track_ids: list[str]) -> None:
        """Remove tracks from the user's library."""
        self._delete("/me/tracks", body={"ids": track_ids})

    def get_recently_played(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recently played tracks."""
        result = self._get("/me/player/recently-played", params={"limit": limit})
        return result.get("items", [])