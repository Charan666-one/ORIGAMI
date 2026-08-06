"""Native macOS Calendar via AppleScript — keyless (no Google API / OAuth).

Creates events reliably (locale-independent date components). Reading events is
slower (AppleScript iterates calendars) but bounded by a timeout. `runner` is
injectable for tests so no osascript runs.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from typing import Callable, List, Optional


class MacCalendarError(Exception):
    pass


class MacCalendar:
    def __init__(self, runner: Optional[Callable[[str], str]] = None) -> None:
        self._runner = runner

    def _run(self, script: str, timeout: int = 40) -> str:
        if self._runner is not None:
            return self._runner(script)
        if sys.platform != "darwin":
            raise MacCalendarError("Calendar control is macOS-only.")
        result = subprocess.run(["osascript", "-e", script],
                                capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            raise MacCalendarError(result.stderr.strip() or "osascript failed")
        return result.stdout.strip()

    def add_event(self, title: str, when: datetime, minutes: int = 60) -> datetime:
        safe = title.replace("\\", "\\\\").replace('"', '\\"')
        script = f"""
set d to current date
set year of d to {when.year}
set month of d to {when.month}
set day of d to {when.day}
set hours of d to {when.hour}
set minutes of d to {when.minute}
set seconds of d to 0
set endD to d + ({minutes} * 60)
tell application "Calendar"
  tell calendar 1
    make new event with properties {{summary:"{safe}", start date:d, end date:endD}}
  end tell
end tell
return "ok"
"""
        self._run(script)
        return when

    def events_today(self) -> List[str]:
        script = """
set startD to current date
set hours of startD to 0
set minutes of startD to 0
set seconds of startD to 0
set endD to startD + (24 * 60 * 60)
set out to ""
tell application "Calendar"
  repeat with cal in calendars
    repeat with e in (every event of cal whose start date is greater than or equal to startD and start date is less than endD)
      set out to out & (summary of e) & " @ " & (time string of (start date of e)) & linefeed
    end repeat
  end repeat
end tell
return out
"""
        text = self._run(script)
        return [ln.strip() for ln in text.splitlines() if ln.strip()]
