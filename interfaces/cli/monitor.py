"""`origami monitor` — the monitoring-mode loop.

Runs continuously, fires a system notification when a reminder is due, and follows
up later to ask whether you finished (accountability + streaks). Keep it running
in a terminal tab or add it as a macOS login item.

It re-reads the task file each tick, so reminders added by separate `origami
"remind me ..."` commands are picked up live.
"""

from __future__ import annotations

import subprocess
import sys
import time

from engines.planning.scheduler import Scheduler


def _as(s: str) -> str:
    # AppleScript string literal — keep unicode literal (JSON \uXXXX escapes break
    # osascript), escape backslashes/quotes, and drop newlines.
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{s}"'


def _notify(title: str, message: str, sound: bool = True) -> None:
    if sys.platform == "darwin":
        snd = ' sound name "Ping"' if sound else ""
        script = f"display notification {_as(message)} with title {_as(title)}{snd}"
        subprocess.run(["osascript", "-e", script], check=False)
    else:
        print(f"\n🔔 [{title}] {message}")


def run_monitor(poll_seconds: int = 30) -> int:
    print("👁  ORIGAMI monitor is running — I'll remind you and keep your streak.")
    print("   (keep this open; press Ctrl+C to stop)\n")
    try:
        while True:
            sched = Scheduler()  # reload so newly-added reminders are seen live
            now = time.time()

            for task in sched.due_now(now):
                tag = "⭐ " if task.important else ""
                _notify("⏰ ORIGAMI Reminder", f"{tag}{task.text}")
                sched.mark_notified(task)
                print(f"[{time.strftime('%H:%M')}] reminded: {task.text}")

            for task in sched.needs_follow_up(now):
                _notify("Did you finish?", f"{task.text}\nRun: origami done {task.text[:24]}")
                sched.mark_followed_up(task)
                print(f"[{time.strftime('%H:%M')}] follow-up: {task.text}")

            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        print("\n👋 Monitor stopped.")
        return 0
