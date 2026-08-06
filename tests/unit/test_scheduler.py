"""Scheduler — due detection, follow-ups, streaks, persistence."""

from __future__ import annotations

import time

from engines.planning.scheduler import FOLLOW_UP_AFTER, Scheduler


def test_due_now_only_past_pending(tmp_path):
    s = Scheduler(path=tmp_path / "t.json")
    s.add("past task", time.time() - 10)
    s.add("future task", time.time() + 3600)
    due = s.due_now()
    assert [t.text for t in due] == ["past task"]


def test_follow_up_after_grace(tmp_path):
    s = Scheduler(path=tmp_path / "t.json")
    t = s.add("write essay", time.time() - FOLLOW_UP_AFTER - 5)
    assert s.needs_follow_up() == []       # not yet notified
    s.mark_notified(t)
    assert len(s.needs_follow_up()) == 1    # notified + past grace -> follow up


def test_mark_done_grows_streak(tmp_path):
    s = Scheduler(path=tmp_path / "t.json")
    s.add("read chapter", time.time())
    assert s.streak == 0
    assert s.mark_done("chapter") is not None
    assert s.streak == 1 and s.pending() == []


def test_follow_up_repeats_until_done(tmp_path):
    s = Scheduler(path=tmp_path / "t.json")
    t = s.add("write essay", time.time() - FOLLOW_UP_AFTER - 5)
    s.mark_notified(t)
    assert len(s.needs_follow_up()) == 1     # first nudge due
    s.mark_followed_up(t)
    assert s.needs_follow_up() == []          # just nudged -> wait
    t.last_nudge = time.time() - FOLLOW_UP_AFTER - 1  # interval elapsed
    assert len(s.needs_follow_up()) == 1     # nudges again (repeats until done)


def test_change_updates_text_keeps_time(tmp_path):
    s = Scheduler(path=tmp_path / "t.json")
    due = time.time() + 3600
    s.add("pay rent", due)
    t = s.change("rent", "get the job you want")
    assert t is not None and t.text == "get the job you want"
    assert abs(t.due - due) < 1              # time unchanged


def test_persistence(tmp_path):
    p = tmp_path / "t.json"
    Scheduler(path=p).add("later", time.time() + 100)
    assert len(Scheduler(path=p).pending()) == 1
