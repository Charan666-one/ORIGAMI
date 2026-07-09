"""
adapters/spotify/auth.py
Spotify OAuth2 (Authorization Code + PKCE) authentication manager.
Falls back to Client Credentials for non-user endpoints.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import time
import urllib.parse
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
DEFAULT_TOKEN_PATH = Path.home() / ".origami" / "tokens" / "spotify.json"

DEFAULT_SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "playlist-read-private",
    "playlist-modify-public",
    "playlist-modify-private",
    "user-library-read",
    "user-library-modify",
    "user-read-recently-played",
]


class SpotifyAuthError(Exception):
    """Raised when Spotify authentication fails."""


class SpotifyAuth:
    """
    Manages Spotify OAuth2 tokens.

    Reads SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET from environment.
    Stores tokens at ~/.origami/tokens/spotify.json.

    Usage:
        auth = SpotifyAuth()
        token = auth.get_access_token()
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: str = "http://localhost:8888/callback",
        scopes: list[str] = DEFAULT_SCOPES,
        token_path: Path = DEFAULT_TOKEN_PATH,
    ) -> None:
        self.client_id = client_id or os.getenv("SPOTIFY_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("SPOTIFY_CLIENT_SECRET", "")
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self.token_path = token_path

        self._token_data: dict = {}

        if not self.client_id or not self.client_secret:
            raise SpotifyAuthError(
                "SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing if expired."""
        self._load_token()

        if self._token_data and not self._is_expired():
            return self._token_data["access_token"]

        if self._token_data.get("refresh_token"):
            self._refresh_token()
            return self._token_data["access_token"]

        # No token at all — run authorization flow
        self._authorize_interactive()
        return self._token_data["access_token"]

    def get_headers(self) -> dict[str, str]:
        """Return Bearer auth headers for Spotify Web API requests."""
        return {
            "Authorization": f"Bearer {self.get_access_token()}",
            "Content-Type": "application/json",
        }

    def revoke(self) -> None:
        """Delete stored token."""
        self._token_data = {}
        if self.token_path.exists():
            self.token_path.unlink()
        logger.info("Spotify token revoked.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _is_expired(self) -> bool:
        expires_at = self._token_data.get("expires_at", 0)
        return time.time() >= expires_at - 30  # 30-second buffer

    def _load_token(self) -> None:
        if not self.token_path.exists():
            return
        try:
            self._token_data = json.loads(self.token_path.read_text())
        except Exception as exc:
            logger.warning("Could not load Spotify token: %s", exc)
            self._token_data = {}

    def _save_token(self) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(json.dumps(self._token_data, indent=2))
        self.token_path.chmod(0o600)

    def _refresh_token(self) -> None:
        refresh_token = self._token_data["refresh_token"]
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        resp = requests.post(SPOTIFY_TOKEN_URL, data=data, timeout=10)
        if resp.status_code != 200:
            raise SpotifyAuthError(f"Token refresh failed: {resp.status_code} {resp.text}")

        new_data = resp.json()
        self._token_data["access_token"] = new_data["access_token"]
        self._token_data["expires_at"] = time.time() + new_data.get("expires_in", 3600)
        # Spotify may or may not return a new refresh token
        if "refresh_token" in new_data:
            self._token_data["refresh_token"] = new_data["refresh_token"]
        self._save_token()
        logger.info("Spotify token refreshed.")

    def _authorize_interactive(self) -> None:
        """
        Run the Authorization Code flow interactively.
        Prints the auth URL and waits for the user to paste the redirect URL.
        """
        # Generate PKCE verifier + challenge
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            )
            .rstrip(b"=")
            .decode()
        )

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
        }
        auth_url = f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}"

        print("\n--- Spotify Authorization Required ---")
        print(f"Open this URL in your browser:\n\n{auth_url}\n")
        redirect_response = input("After authorizing, paste the full redirect URL here: ").strip()

        # Extract authorization code from redirect URL
        parsed = urllib.parse.urlparse(redirect_response)
        qs = urllib.parse.parse_qs(parsed.query)
        code = qs.get("code", [None])[0]
        if not code:
            raise SpotifyAuthError("No authorization code found in redirect URL.")

        # Exchange code for tokens
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": code_verifier,
        }
        resp = requests.post(SPOTIFY_TOKEN_URL, data=data, timeout=10)
        if resp.status_code != 200:
            raise SpotifyAuthError(f"Token exchange failed: {resp.status_code} {resp.text}")

        token_data = resp.json()
        token_data["expires_at"] = time.time() + token_data.get("expires_in", 3600)
        self._token_data = token_data
        self._save_token()
        logger.info("Spotify authorization complete.")