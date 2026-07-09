"""
adapters/github/auth.py
GitHub authentication — supports Personal Access Token (PAT) and
GitHub App (JWT + installation token) strategies.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import jwt  # PyJWT
import requests

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubAuthError(Exception):
    """Raised when GitHub authentication fails."""


class GitHubAuth:
    """
    Authentication manager for GitHub API.

    Supports two modes:
      1. PAT (Personal Access Token) — simplest, set GITHUB_TOKEN env var.
      2. GitHub App — uses private key + app ID to generate installation tokens.

    Usage (PAT mode):
        auth = GitHubAuth()          # reads GITHUB_TOKEN from env
        headers = auth.get_headers()

    Usage (App mode):
        auth = GitHubAuth(
            app_id="123456",
            private_key_path="/path/to/private.pem",
            installation_id="789"
        )
        headers = auth.get_headers()
    """

    def __init__(
        self,
        token: Optional[str] = None,
        app_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
        installation_id: Optional[str] = None,
    ) -> None:
        self._pat = token or os.getenv("GITHUB_TOKEN")
        self._app_id = app_id or os.getenv("GITHUB_APP_ID")
        self._private_key_path = private_key_path or os.getenv("GITHUB_PRIVATE_KEY_PATH")
        self._installation_id = installation_id or os.getenv("GITHUB_INSTALLATION_ID")

        # Cache for installation token + its expiry epoch
        self._installation_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        self._validate_config()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_headers(self) -> dict[str, str]:
        """Return Authorization headers suitable for requests/httpx."""
        token = self._resolve_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def get_token(self) -> str:
        """Return the active bearer token string."""
        return self._resolve_token()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        has_pat = bool(self._pat)
        has_app = bool(self._app_id and self._private_key_path and self._installation_id)
        if not has_pat and not has_app:
            raise GitHubAuthError(
                "GitHub auth not configured. Set GITHUB_TOKEN env var (PAT mode) "
                "or GITHUB_APP_ID + GITHUB_PRIVATE_KEY_PATH + GITHUB_INSTALLATION_ID "
                "(App mode)."
            )

    def _resolve_token(self) -> str:
        """Determine which auth strategy to use and return a valid token."""
        if self._pat:
            return self._pat
        return self._get_installation_token()

    def _get_installation_token(self) -> str:
        """Return a cached or freshly generated GitHub App installation token."""
        # Tokens expire after 1 hour; refresh 60 seconds early
        if self._installation_token and time.time() < self._token_expires_at - 60:
            return self._installation_token

        jwt_token = self._generate_jwt()
        url = f"{GITHUB_API_BASE}/app/installations/{self._installation_id}/access_tokens"
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10,
        )
        if resp.status_code != 201:
            raise GitHubAuthError(
                f"Failed to get installation token: {resp.status_code} {resp.text}"
            )
        data = resp.json()
        self._installation_token = data["token"]
        # expires_at is ISO 8601; convert to epoch for comparison
        from datetime import datetime, timezone
        expires_at_str = data.get("expires_at", "")
        try:
            self._token_expires_at = datetime.fromisoformat(
                expires_at_str.replace("Z", "+00:00")
            ).timestamp()
        except Exception:
            self._token_expires_at = time.time() + 3600  # fallback: 1 hour

        logger.info("GitHub App installation token refreshed.")
        return self._installation_token

    def _generate_jwt(self) -> str:
        """Generate a short-lived JWT for GitHub App authentication."""
        if not self._private_key_path:
            raise GitHubAuthError("GITHUB_PRIVATE_KEY_PATH not set.")
        try:
            with open(self._private_key_path, "r") as f:
                private_key = f.read()
        except OSError as exc:
            raise GitHubAuthError(f"Cannot read private key: {exc}") from exc

        now = int(time.time())
        payload = {
            "iat": now - 60,   # issued at (60s in past for clock skew)
            "exp": now + 600,  # expires in 10 minutes
            "iss": self._app_id,
        }
        try:
            token = jwt.encode(payload, private_key, algorithm="RS256")
            return token if isinstance(token, str) else token.decode("utf-8")
        except Exception as exc:
            raise GitHubAuthError(f"JWT generation failed: {exc}") from exc