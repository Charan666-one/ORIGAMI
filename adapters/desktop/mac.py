"""
adapters/desktop/mac.py
macOS desktop automation adapter using AppleScript and osascript.
Provides: app control, window management, notifications, clipboard, screenshots.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class MacDesktopError(Exception):
    """Raised when a macOS automation action fails."""


def _run_applescript(script: str, timeout: int = 10) -> str:
    """Execute an AppleScript string via osascript and return stdout."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise MacDesktopError(f"AppleScript error: {result.stderr.strip()}")
    return result.stdout.strip()


def _run_shell(cmd: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


class MacDesktopAdapter:
    """
    macOS desktop automation using AppleScript + system commands.

    Usage:
        mac = MacDesktopAdapter()
        mac.open_application("Safari")
        mac.send_notification("ORIGAMI", "Task complete!")
    """

    # ------------------------------------------------------------------
    # Application Control
    # ------------------------------------------------------------------

    def open_application(self, app_name: str) -> None:
        """Open a macOS application by name."""
        result = _run_shell(["open", "-a", app_name])
        if result.returncode != 0:
            raise MacDesktopError(f"Failed to open '{app_name}': {result.stderr.strip()}")
        logger.info("Opened application: %s", app_name)

    def quit_application(self, app_name: str) -> None:
        """Quit a running application gracefully."""
        _run_applescript(f'tell application "{app_name}" to quit')
        logger.info("Quit application: %s", app_name)

    def is_running(self, app_name: str) -> bool:
        """Check whether an application is currently running."""
        script = (
            f'tell application "System Events" to '
            f'(name of processes) contains "{app_name}"'
        )
        try:
            return _run_applescript(script) == "true"
        except MacDesktopError:
            return False

    def list_running_apps(self) -> list[str]:
        """Return names of all running GUI applications."""
        script = (
            'tell application "System Events" to '
            'get name of every application process whose background only is false'
        )
        result = _run_applescript(script)
        return [a.strip() for a in result.split(",") if a.strip()]

    def focus_application(self, app_name: str) -> None:
        """Bring an application to the foreground."""
        _run_applescript(f'tell application "{app_name}" to activate')
        logger.info("Focused application: %s", app_name)

    # ------------------------------------------------------------------
    # Window Management
    # ------------------------------------------------------------------

    def minimize_window(self, app_name: str) -> None:
        """Minimize the frontmost window of an application."""
        script = (
            f'tell application "{app_name}" to '
            f'set miniaturized of front window to true'
        )
        _run_applescript(script)

    def maximize_window(self, app_name: str) -> None:
        """Set a window to its zoomed (full) state."""
        script = (
            f'tell application "{app_name}" to '
            f'set zoomed of front window to true'
        )
        _run_applescript(script)

    def close_window(self, app_name: str) -> None:
        """Close the front window of an application."""
        _run_applescript(f'tell application "{app_name}" to close front window')

    def get_window_title(self, app_name: str) -> str:
        """Get the title of the frontmost window."""
        script = f'tell application "{app_name}" to get name of front window'
        return _run_applescript(script)

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def send_notification(
        self,
        title: str,
        message: str,
        subtitle: str = "",
        sound: str = "default",
    ) -> None:
        """
        Send a macOS system notification.

        Args:
            title: Notification title.
            message: Notification body text.
            subtitle: Optional subtitle line.
            sound: Sound name ('default', 'Glass', 'Pop', etc.) or '' for silent.
        """
        subtitle_part = f' subtitle "{subtitle}"' if subtitle else ""
        sound_part = f' sound name "{sound}"' if sound else ""
        script = (
            f'display notification "{message}" '
            f'with title "{title}"{subtitle_part}{sound_part}'
        )
        _run_applescript(script)
        logger.info("Sent notification: [%s] %s", title, message)

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------

    def get_clipboard(self) -> str:
        """Return the current clipboard contents as text."""
        result = _run_shell(["pbpaste"])
        return result.stdout

    def set_clipboard(self, text: str) -> None:
        """Set clipboard contents."""
        proc = subprocess.run(["pbcopy"], input=text, text=True)
        if proc.returncode != 0:
            raise MacDesktopError("Failed to set clipboard.")
        logger.debug("Clipboard updated.")

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    def take_screenshot(self, output_path: Optional[Path] = None, window: bool = False) -> Path:
        """
        Capture a screenshot.

        Args:
            output_path: Where to save the PNG file. Defaults to ~/Desktop.
            window: If True, capture only the active window (interactive).
        """
        if output_path is None:
            output_path = Path.home() / "Desktop" / "origami_screenshot.png"
        cmd = ["screencapture", "-x"]  # -x = no sound
        if window:
            cmd.append("-w")  # interactive window capture
        cmd.append(str(output_path))
        result = _run_shell(cmd)
        if result.returncode != 0:
            raise MacDesktopError(f"Screenshot failed: {result.stderr.strip()}")
        logger.info("Screenshot saved to %s", output_path)
        return output_path

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------

    def lock_screen(self) -> None:
        """Lock the screen immediately."""
        _run_shell([
            "osascript", "-e",
            'tell application "System Events" to keystroke "q" '
            'using {command down, control down}'
        ])

    def set_volume(self, level: int) -> None:
        """
        Set system output volume.

        Args:
            level: Volume level 0-100.
        """
        level = max(0, min(100, level))
        _run_applescript(f"set volume output volume {level}")
        logger.info("System volume set to %d.", level)

    def get_volume(self) -> int:
        """Get current system output volume (0-100)."""
        result = _run_applescript("output volume of (get volume settings)")
        try:
            return int(result)
        except ValueError:
            return 0

    def mute(self) -> None:
        """Mute system audio."""
        _run_applescript("set volume output muted true")

    def unmute(self) -> None:
        """Unmute system audio."""
        _run_applescript("set volume output muted false")

    def shutdown(self, delay_seconds: int = 0) -> None:
        """Initiate system shutdown (requires appropriate permissions)."""
        _run_shell(["shutdown", "-h", f"+{delay_seconds // 60}" if delay_seconds else "now"])

    def sleep(self) -> None:
        """Put the Mac to sleep."""
        _run_shell(["pmset", "sleepnow"])

    # ------------------------------------------------------------------
    # Browser helpers (Safari / Chrome)
    # ------------------------------------------------------------------

    def open_url(self, url: str, browser: str = "Safari") -> None:
        """Open a URL in the specified browser."""
        if browser.lower() == "safari":
            _run_applescript(
                f'tell application "Safari" to open location "{url}"'
            )
        elif browser.lower() in ("chrome", "google chrome"):
            _run_applescript(
                f'tell application "Google Chrome" to open location "{url}"'
            )
        else:
            # Fall back to system default
            _run_shell(["open", url])
        logger.info("Opened URL: %s in %s.", url, browser)

    # ------------------------------------------------------------------
    # Spotlight / Search
    # ------------------------------------------------------------------

    def spotlight_search(self, query: str) -> None:
        """Open Spotlight with a pre-filled query."""
        script = (
            'tell application "System Events" to keystroke " " using command down\n'
            f'delay 0.5\n'
            f'tell application "System Events" to keystroke "{query}"'
        )
        _run_applescript(script)