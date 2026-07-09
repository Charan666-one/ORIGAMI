"""
adapters/calendar/auth.py
Google Calendar OAuth2 authentication handler.
Handles token acquisition, refresh, and secure storage.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

# Scopes required for read/write calendar access
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]

DEFAULT_TOKEN_PATH = Path.home() / ".origami" / "tokens" / "google_calendar.json"
DEFAULT_CREDS_PATH = Path(os.getenv("GOOGLE_CREDENTIALS_PATH", "configs/secrets/google_credentials.json"))


class CalendarAuthError(Exception):
    """Raised when authentication fails or token cannot be refreshed."""


class CalendarAuth:
    """
    Manages Google Calendar OAuth2 credentials lifecycle.

    Usage:
        auth = CalendarAuth()
        creds = auth.get_credentials()
    """

    def __init__(
        self,
        credentials_path: Path = DEFAULT_CREDS_PATH,
        token_path: Path = DEFAULT_TOKEN_PATH,
        scopes: list[str] = SCOPES,
    ) -> None:
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.scopes = scopes
        self._credentials: Optional[Credentials] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_credentials(self) -> Credentials:
        """Return valid credentials, refreshing or re-authorising as needed."""
        creds = self._load_token()

        if creds and creds.valid:
            self._credentials = creds
            return creds

        if creds and creds.expired and creds.refresh_token:
            creds = self._refresh(creds)
            self._save_token(creds)
            self._credentials = creds
            return creds

        # No valid token — trigger browser-based OAuth flow
        creds = self._authorize()
        self._save_token(creds)
        self._credentials = creds
        return creds

    def revoke(self) -> None:
        """Delete stored token, forcing re-authentication on next use."""
        if self.token_path.exists():
            self.token_path.unlink()
            logger.info("Calendar token revoked and deleted.")
        self._credentials = None

    @property
    def is_authenticated(self) -> bool:
        """True if there are currently valid cached credentials."""
        return self._credentials is not None and self._credentials.valid

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_token(self) -> Optional[Credentials]:
        """Load credentials from disk if the token file exists."""
        if not self.token_path.exists():
            return None
        try:
            creds = Credentials.from_authorized_user_file(str(self.token_path), self.scopes)
            logger.debug("Loaded calendar token from %s", self.token_path)
            return creds
        except Exception as exc:
            logger.warning("Failed to load calendar token: %s", exc)
            return None

    def _refresh(self, creds: Credentials) -> Credentials:
        """Attempt to refresh an expired token."""
        try:
            creds.refresh(Request())
            logger.info("Calendar token refreshed successfully.")
            return creds
        except Exception as exc:
            raise CalendarAuthError(f"Token refresh failed: {exc}") from exc

    def _authorize(self) -> Credentials:
        """Run the browser-based OAuth flow to get fresh credentials."""
        if not self.credentials_path.exists():
            raise CalendarAuthError(
                f"Google credentials file not found at {self.credentials_path}. "
                "Download it from Google Cloud Console and place it there."
            )
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path), self.scopes
            )
            creds = flow.run_local_server(port=0)
            logger.info("Google Calendar authorization successful.")
            return creds
        except Exception as exc:
            raise CalendarAuthError(f"OAuth flow failed: {exc}") from exc

    def _save_token(self, creds: Credentials) -> None:
        """Persist credentials to disk for future sessions."""
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds.to_json())
        # Restrict file permissions to owner only
        self.token_path.chmod(0o600)
        logger.debug("Calendar token saved to %s", self.token_path)