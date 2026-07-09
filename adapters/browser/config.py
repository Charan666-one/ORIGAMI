"""
adapters/browser/config.py
Configuration dataclass for BrowserController.
Load from YAML or environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class BrowserConfig:
    """
    Configuration for BrowserController.

    Fields sourced from configs/engines/browser.yaml or environment variables.
    Environment variables take precedence over YAML values.

    Example YAML:
        browser:
          headless: true
          type: chromium
          timeout_ms: 30000
          user_data_dir: ~/.origami/browser_profile
          downloads_dir: ~/Downloads/origami
          viewport_width: 1280
          viewport_height: 720
          locale: en-IN
          timezone: Asia/Kolkata
          ignore_https_errors: false
          proxy: ""
    """

    # Core
    headless: bool = True
    browser_type: str = "chromium"          # chromium | firefox | webkit
    timeout_ms: int = 30_000

    # Storage
    user_data_dir: Optional[Path] = None    # Persistent profile (keeps sessions)
    downloads_dir: Path = field(
        default_factory=lambda: Path.home() / "Downloads" / "origami"
    )

    # Viewport
    viewport_width: int = 1280
    viewport_height: int = 720

    # Locale
    locale: str = "en-IN"
    timezone: str = "Asia/Kolkata"

    # Security
    ignore_https_errors: bool = False

    # Proxy (optional: "http://user:pass@host:port")
    proxy: Optional[str] = None

    # Stealth / anti-bot
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "BrowserConfig":
        """
        Build config from environment variables.

        Supported env vars:
            BROWSER_HEADLESS          : '1' / 'true' / '0' / 'false'
            BROWSER_TYPE              : chromium | firefox | webkit
            BROWSER_TIMEOUT_MS        : integer
            BROWSER_USER_DATA_DIR     : path string
            BROWSER_DOWNLOADS_DIR     : path string
            BROWSER_VIEWPORT_WIDTH    : integer
            BROWSER_VIEWPORT_HEIGHT   : integer
            BROWSER_LOCALE            : e.g. en-IN
            BROWSER_TIMEZONE          : e.g. Asia/Kolkata
            BROWSER_IGNORE_HTTPS      : '1' / '0'
            BROWSER_PROXY             : proxy URL string
        """
        def _bool(key: str, default: bool) -> bool:
            val = os.getenv(key, "").lower()
            if val in ("1", "true", "yes"):
                return True
            if val in ("0", "false", "no"):
                return False
            return default

        def _int(key: str, default: int) -> int:
            try:
                return int(os.getenv(key, str(default)))
            except ValueError:
                return default

        def _path(key: str, default: Optional[Path]) -> Optional[Path]:
            val = os.getenv(key)
            return Path(val).expanduser() if val else default

        return cls(
            headless=_bool("BROWSER_HEADLESS", True),
            browser_type=os.getenv("BROWSER_TYPE", "chromium"),
            timeout_ms=_int("BROWSER_TIMEOUT_MS", 30_000),
            user_data_dir=_path("BROWSER_USER_DATA_DIR", None),
            downloads_dir=_path(
                "BROWSER_DOWNLOADS_DIR",
                Path.home() / "Downloads" / "origami",
            ),
            viewport_width=_int("BROWSER_VIEWPORT_WIDTH", 1280),
            viewport_height=_int("BROWSER_VIEWPORT_HEIGHT", 720),
            locale=os.getenv("BROWSER_LOCALE", "en-IN"),
            timezone=os.getenv("BROWSER_TIMEZONE", "Asia/Kolkata"),
            ignore_https_errors=_bool("BROWSER_IGNORE_HTTPS", False),
            proxy=os.getenv("BROWSER_PROXY") or None,
        )

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "BrowserConfig":
        """Load config from a YAML file."""
        import yaml  # pyyaml

        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f) or {}

        browser_cfg = data.get("browser", {})

        def _path_or_none(val) -> Optional[Path]:
            return Path(val).expanduser() if val else None

        return cls(
            headless=browser_cfg.get("headless", True),
            browser_type=browser_cfg.get("type", "chromium"),
            timeout_ms=browser_cfg.get("timeout_ms", 30_000),
            user_data_dir=_path_or_none(browser_cfg.get("user_data_dir")),
            downloads_dir=_path_or_none(browser_cfg.get("downloads_dir"))
            or Path.home() / "Downloads" / "origami",
            viewport_width=browser_cfg.get("viewport_width", 1280),
            viewport_height=browser_cfg.get("viewport_height", 720),
            locale=browser_cfg.get("locale", "en-IN"),
            timezone=browser_cfg.get("timezone", "Asia/Kolkata"),
            ignore_https_errors=browser_cfg.get("ignore_https_errors", False),
            proxy=browser_cfg.get("proxy") or None,
            user_agent=browser_cfg.get("user_agent", cls.user_agent),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def to_playwright_launch_kwargs(self) -> dict:
        """Return kwargs suitable for playwright browser.launch()."""
        kwargs: dict = {"headless": self.headless}
        if self.proxy:
            kwargs["proxy"] = {"server": self.proxy}
        return kwargs

    def to_playwright_context_kwargs(self) -> dict:
        """Return kwargs for browser.new_context()."""
        kwargs: dict = {
            "viewport": {"width": self.viewport_width, "height": self.viewport_height},
            "locale": self.locale,
            "timezone_id": self.timezone,
            "ignore_https_errors": self.ignore_https_errors,
            "user_agent": self.user_agent,
            "accept_downloads": True,
        }
        if self.downloads_dir:
            self.downloads_dir.mkdir(parents=True, exist_ok=True)
        return kwargs