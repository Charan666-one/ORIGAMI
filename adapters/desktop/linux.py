"""
adapters/desktop/linux.py
Linux desktop automation adapter using xdotool, wmctrl, notify-send, xclip.
Supports X11 environments (GNOME, KDE, XFCE, i3, etc.).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class LinuxDesktopError(Exception):
    """Raised when a Linux desktop automation action fails."""


def _require_tool(name: str) -> str:
    """Return path to tool or raise if not installed."""
    path = shutil.which(name)
    if not path:
        raise LinuxDesktopError(
            f"'{name}' is not installed. Install it with your package manager "
            f"(e.g. apt install {name})."
        )
    return path


def _run(cmd: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


class LinuxDesktopAdapter:
    """
    Linux desktop automation using standard CLI tools.

    Required tools (install as needed):
        xdotool, wmctrl, notify-send, xclip, scrot, pactl/amixer

    Usage:
        linux = LinuxDesktopAdapter()
        linux.open_application("gedit")
        linux.send_notification("ORIGAMI", "Hello!")
    """

    # ------------------------------------------------------------------
    # Application Control
    # ------------------------------------------------------------------

    def open_application(self, app_name: str, args: Optional[list[str]] = None) -> None:
        """Launch an application."""
        cmd = [app_name] + (args or [])
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("Launched: %s", app_name)
        except FileNotFoundError:
            raise LinuxDesktopError(
                f"Application '{app_name}' not found. Is it installed and on PATH?"
            )

    def quit_application(self, process_name: str) -> None:
        """Kill all processes matching the given name."""
        result = _run(["pkill", "-f", process_name])
        if result.returncode not in (0, 1):  # 1 = no processes found
            raise LinuxDesktopError(f"pkill failed for '{process_name}': {result.stderr}")
        logger.info("Killed process: %s", process_name)

    def is_running(self, process_name: str) -> bool:
        """Return True if any process with the given name is running."""
        result = _run(["pgrep", "-f", process_name])
        return result.returncode == 0

    def list_windows(self) -> list[dict]:
        """Return a list of open windows (requires wmctrl)."""
        _require_tool("wmctrl")
        result = _run(["wmctrl", "-l"])
        windows = []
        for line in result.stdout.strip().splitlines():
            parts = line.split(None, 3)
            if len(parts) == 4:
                windows.append({
                    "id": parts[0],
                    "desktop": parts[1],
                    "host": parts[2],
                    "title": parts[3],
                })
        return windows

    def focus_window_by_title(self, title_substring: str) -> bool:
        """Bring the first matching window to the foreground using wmctrl."""
        _require_tool("wmctrl")
        result = _run(["wmctrl", "-a", title_substring])
        if result.returncode == 0:
            logger.info("Focused window containing: %s", title_substring)
            return True
        return False

    def minimize_active_window(self) -> None:
        """Minimize the currently active window using xdotool."""
        _require_tool("xdotool")
        _run(["xdotool", "getactivewindow", "windowminimize"])

    def close_window_by_title(self, title_substring: str) -> bool:
        """Close first window whose title contains the substring."""
        _require_tool("wmctrl")
        for w in self.list_windows():
            if title_substring.lower() in w["title"].lower():
                _run(["wmctrl", "-ic", w["id"]])
                logger.info("Closed window: %s", w["title"])
                return True
        return False

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def send_notification(
        self,
        title: str,
        message: str,
        urgency: str = "normal",
        expire_ms: int = 5000,
        icon: str = "dialog-information",
    ) -> None:
        """
        Send a desktop notification using notify-send.

        Args:
            title: Notification title.
            message: Notification body.
            urgency: 'low', 'normal', or 'critical'.
            expire_ms: Auto-dismiss timeout in milliseconds.
            icon: Icon name or path.
        """
        _require_tool("notify-send")
        _run([
            "notify-send",
            "--urgency", urgency,
            "--expire-time", str(expire_ms),
            "--icon", icon,
            title,
            message,
        ])
        logger.info("Sent notification: [%s] %s", title, message)

    # ------------------------------------------------------------------
    # Clipboard (xclip)
    # ------------------------------------------------------------------

    def get_clipboard(self) -> str:
        """Return current clipboard text."""
        _require_tool("xclip")
        result = _run(["xclip", "-selection", "clipboard", "-o"])
        if result.returncode != 0:
            raise LinuxDesktopError(f"xclip read failed: {result.stderr}")
        return result.stdout

    def set_clipboard(self, text: str) -> None:
        """Set clipboard contents."""
        _require_tool("xclip")
        proc = subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text,
            text=True,
        )
        if proc.returncode != 0:
            raise LinuxDesktopError("xclip write failed.")
        logger.debug("Clipboard updated.")

    # ------------------------------------------------------------------
    # Screenshot (scrot or gnome-screenshot)
    # ------------------------------------------------------------------

    def take_screenshot(
        self,
        output_path: Optional[Path] = None,
        delay: int = 0,
        focused_window: bool = False,
    ) -> Path:
        """
        Capture a screenshot.

        Args:
            output_path: Save path. Defaults to ~/Desktop/origami_screenshot.png.
            delay: Seconds to wait before capturing.
            focused_window: Capture only the focused window if True.
        """
        if output_path is None:
            output_path = Path.home() / "Desktop" / "origami_screenshot.png"

        if shutil.which("scrot"):
            cmd = ["scrot", str(output_path)]
            if delay:
                cmd += ["-d", str(delay)]
            if focused_window:
                cmd.append("-u")
            _run(cmd)
        elif shutil.which("gnome-screenshot"):
            cmd = ["gnome-screenshot", "-f", str(output_path)]
            if delay:
                cmd += ["-d", str(delay)]
            if focused_window:
                cmd.append("-w")
            _run(cmd)
        else:
            raise LinuxDesktopError(
                "No screenshot tool found. Install scrot: apt install scrot"
            )

        logger.info("Screenshot saved to %s", output_path)
        return output_path

    # ------------------------------------------------------------------
    # Volume (pactl / amixer)
    # ------------------------------------------------------------------

    def set_volume(self, level: int) -> None:
        """
        Set system volume using pactl or amixer.

        Args:
            level: Volume 0-100.
        """
        level = max(0, min(100, level))
        if shutil.which("pactl"):
            _run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"])
        elif shutil.which("amixer"):
            _run(["amixer", "-q", "sset", "Master", f"{level}%"])
        else:
            raise LinuxDesktopError("No volume control tool found (pactl or amixer).")
        logger.info("Volume set to %d%%.", level)

    def get_volume(self) -> int:
        """Get current output volume (0-100). Requires pactl."""
        if not shutil.which("pactl"):
            raise LinuxDesktopError("pactl not found.")
        result = _run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        # Parse "Volume: ... 75% ..." 
        for part in result.stdout.split():
            if part.endswith("%"):
                try:
                    return int(part.rstrip("%"))
                except ValueError:
                    pass
        return 0

    def mute(self) -> None:
        """Mute system audio."""
        if shutil.which("pactl"):
            _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"])
        else:
            _run(["amixer", "-q", "sset", "Master", "mute"])

    def unmute(self) -> None:
        """Unmute system audio."""
        if shutil.which("pactl"):
            _run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"])
        else:
            _run(["amixer", "-q", "sset", "Master", "unmute"])

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------

    def lock_screen(self) -> None:
        """Lock the screen (tries common lock commands)."""
        for cmd in [
            ["gnome-screensaver-command", "--lock"],
            ["xdg-screensaver", "lock"],
            ["xscreensaver-command", "-lock"],
            ["loginctl", "lock-session"],
        ]:
            if shutil.which(cmd[0]):
                _run(cmd)
                return
        raise LinuxDesktopError("No screen lock command found.")

    def shutdown(self, delay_minutes: int = 0) -> None:
        """Schedule system shutdown."""
        _run(["shutdown", "-h", f"+{delay_minutes}" if delay_minutes else "now"])

    def restart(self, delay_minutes: int = 0) -> None:
        """Schedule system restart."""
        _run(["shutdown", "-r", f"+{delay_minutes}" if delay_minutes else "now"])

    def sleep(self) -> None:
        """Suspend the system."""
        _run(["systemctl", "suspend"])

    # ------------------------------------------------------------------
    # Open URL
    # ------------------------------------------------------------------

    def open_url(self, url: str) -> None:
        """Open a URL in the default browser."""
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info("Opened URL: %s", url)

    def open_file(self, file_path: str) -> None:
        """Open a file with its default application."""
        subprocess.Popen(["xdg-open", file_path])
        logger.info("Opened file: %s", file_path)

    # ------------------------------------------------------------------
    # Key/Mouse simulation (xdotool)
    # ------------------------------------------------------------------

    def type_text(self, text: str, delay_ms: int = 0) -> None:
        """Type text at the current cursor position using xdotool."""
        _require_tool("xdotool")
        cmd = ["xdotool", "type"]
        if delay_ms:
            cmd += ["--delay", str(delay_ms)]
        cmd.append(text)
        _run(cmd)

    def press_key(self, key: str) -> None:
        """
        Simulate a key press using xdotool.

        Args:
            key: Key name in xdotool format (e.g. 'Return', 'ctrl+c', 'super').
        """
        _require_tool("xdotool")
        _run(["xdotool", "key", key])