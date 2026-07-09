"""
adapters/desktop/windows.py
Windows desktop automation adapter using pywin32, pyautogui, and winreg.
Provides: app control, window management, notifications, clipboard, screenshots.
"""

from __future__ import annotations

import ctypes
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class WindowsDesktopError(Exception):
    """Raised when a Windows automation action fails."""


def _check_windows() -> None:
    if os.name != "nt":
        raise WindowsDesktopError("WindowsDesktopAdapter can only run on Windows.")


class WindowsDesktopAdapter:
    """
    Windows desktop automation adapter.

    Dependencies:
        pip install pywin32 pyautogui pillow win10toast

    Usage:
        win = WindowsDesktopAdapter()
        win.open_application("notepad.exe")
        win.send_notification("ORIGAMI", "Task done!")
    """

    def __init__(self) -> None:
        _check_windows()
        # Lazy imports — only available on Windows
        try:
            import win32gui
            import win32con
            import win32process
            import win32api
            self._win32gui = win32gui
            self._win32con = win32con
            self._win32process = win32process
            self._win32api = win32api
        except ImportError:
            raise WindowsDesktopError(
                "pywin32 is not installed. Run: pip install pywin32"
            )

    # ------------------------------------------------------------------
    # Application Control
    # ------------------------------------------------------------------

    def open_application(self, executable: str, args: str = "") -> None:
        """
        Launch an application.

        Args:
            executable: Path or name of the executable (e.g. 'notepad.exe').
            args: Optional command-line arguments.
        """
        cmd = f'"{executable}" {args}'.strip()
        try:
            subprocess.Popen(cmd, shell=True)
            logger.info("Launched: %s", executable)
        except Exception as exc:
            raise WindowsDesktopError(f"Failed to launch '{executable}': {exc}") from exc

    def quit_application(self, process_name: str) -> None:
        """Terminate all processes with the given name."""
        subprocess.run(
            ["taskkill", "/f", "/im", process_name],
            capture_output=True,
            check=True,
        )
        logger.info("Terminated process: %s", process_name)

    def is_running(self, process_name: str) -> bool:
        """Return True if a process with the given name is running."""
        result = subprocess.run(
            ["tasklist", "/fi", f"imagename eq {process_name}"],
            capture_output=True,
            text=True,
        )
        return process_name.lower() in result.stdout.lower()

    def list_windows(self) -> list[dict]:
        """Return a list of visible window titles and handles."""
        windows = []

        def _enum_handler(hwnd, ctx):
            if self._win32gui.IsWindowVisible(hwnd):
                title = self._win32gui.GetWindowText(hwnd)
                if title:
                    windows.append({"hwnd": hwnd, "title": title})

        self._win32gui.EnumWindows(_enum_handler, None)
        return windows

    def focus_window_by_title(self, title_substring: str) -> bool:
        """
        Bring the first window whose title contains the given substring
        to the foreground.

        Returns True if a window was found and focused.
        """
        for w in self.list_windows():
            if title_substring.lower() in w["title"].lower():
                hwnd = w["hwnd"]
                self._win32gui.ShowWindow(hwnd, self._win32con.SW_RESTORE)
                self._win32gui.SetForegroundWindow(hwnd)
                logger.info("Focused window: %s", w["title"])
                return True
        return False

    def minimize_window(self, title_substring: str) -> bool:
        """Minimize the first matching window."""
        for w in self.list_windows():
            if title_substring.lower() in w["title"].lower():
                self._win32gui.ShowWindow(w["hwnd"], self._win32con.SW_MINIMIZE)
                return True
        return False

    def close_window(self, title_substring: str) -> bool:
        """Close the first matching window."""
        for w in self.list_windows():
            if title_substring.lower() in w["title"].lower():
                self._win32gui.PostMessage(
                    w["hwnd"], self._win32con.WM_CLOSE, 0, 0
                )
                logger.info("Closed window: %s", w["title"])
                return True
        return False

    # ------------------------------------------------------------------
    # Notifications (Windows 10/11 Toast)
    # ------------------------------------------------------------------

    def send_notification(
        self,
        title: str,
        message: str,
        duration: int = 5,
        icon_path: Optional[str] = None,
    ) -> None:
        """
        Send a Windows 10/11 toast notification.

        Requires: pip install win10toast
        """
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(
                title,
                message,
                icon_path=icon_path,
                duration=duration,
                threaded=True,
            )
            logger.info("Sent notification: [%s] %s", title, message)
        except ImportError:
            # Fallback: use ctypes MessageBox (blocking)
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------

    def get_clipboard(self) -> str:
        """Return current clipboard text."""
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            finally:
                win32clipboard.CloseClipboard()
            return data
        except Exception as exc:
            raise WindowsDesktopError(f"Failed to read clipboard: {exc}") from exc

    def set_clipboard(self, text: str) -> None:
        """Set clipboard contents to text."""
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
            finally:
                win32clipboard.CloseClipboard()
            logger.debug("Clipboard set.")
        except Exception as exc:
            raise WindowsDesktopError(f"Failed to set clipboard: {exc}") from exc

    # ------------------------------------------------------------------
    # Screenshot
    # ------------------------------------------------------------------

    def take_screenshot(self, output_path: Optional[Path] = None) -> Path:
        """
        Capture a full-screen screenshot.

        Args:
            output_path: Where to save the PNG. Defaults to Desktop.
        """
        try:
            import pyautogui
        except ImportError:
            raise WindowsDesktopError("pyautogui not installed. Run: pip install pyautogui pillow")

        if output_path is None:
            output_path = Path.home() / "Desktop" / "origami_screenshot.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(str(output_path))
        logger.info("Screenshot saved to %s", output_path)
        return output_path

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------

    def set_volume(self, level: int) -> None:
        """
        Set system master volume via nircmd or PowerShell.

        Args:
            level: 0-100.
        """
        level = max(0, min(100, level))
        # Use PowerShell to set audio level (no external tool required)
        ps_script = (
            f"[audio.volume]::SetMasterVolumeLevelScalar({level / 100:.2f}, [guid]::Empty)"
        )
        # Simpler: use nircmd if available
        nircmd = shutil.which("nircmd")
        if nircmd:
            subprocess.run([nircmd, "setsysvolume", str(int(level * 655.35))])
        else:
            subprocess.run(
                ["powershell", "-Command",
                 f"$obj = New-Object -com 'wscript.shell'; $obj.SendKeys([char]175)"],
                capture_output=True,
            )
        logger.info("Volume set to %d.", level)

    def lock_screen(self) -> None:
        """Lock the Windows workstation."""
        ctypes.windll.user32.LockWorkStation()

    def shutdown(self, delay_seconds: int = 0) -> None:
        """Schedule a system shutdown."""
        subprocess.run(["shutdown", "/s", "/t", str(delay_seconds)])

    def restart(self, delay_seconds: int = 0) -> None:
        """Schedule a system restart."""
        subprocess.run(["shutdown", "/r", "/t", str(delay_seconds)])

    def sleep(self) -> None:
        """Put the system to sleep."""
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])

    # ------------------------------------------------------------------
    # Open URL
    # ------------------------------------------------------------------

    def open_url(self, url: str) -> None:
        """Open a URL in the default browser."""
        os.startfile(url)
        logger.info("Opened URL: %s", url)

    def open_file(self, file_path: str) -> None:
        """Open a file with its default application."""
        os.startfile(file_path)
        logger.info("Opened file: %s", file_path)


# Avoid NameError on non-Windows when importing module
try:
    import shutil
except ImportError:
    pass