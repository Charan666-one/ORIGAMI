"""Atomic persistence + resilience to a corrupted store."""

from __future__ import annotations

from core.persist import atomic_write_json, read_text
from engines.memory.engine import JSONMemory
from engines.planning.scheduler import Scheduler


def test_atomic_write_and_read(tmp_path):
    p = tmp_path / "x.json"
    atomic_write_json(p, {"a": 1})
    assert '"a": 1' in read_text(p)
    assert not (tmp_path / "x.json.tmp").exists()   # temp cleaned up


def test_read_text_missing_returns_default(tmp_path):
    assert read_text(tmp_path / "nope.json", default="{}") == "{}"


def test_stores_survive_corrupted_file(tmp_path):
    # a truncated/garbage file must not crash — load returns empty, not an exception
    bad = tmp_path / "mem.json"
    bad.write_text('[{"text": "half', encoding="utf-8")
    assert JSONMemory(path=bad).all() == []

    bad2 = tmp_path / "tasks.json"
    bad2.write_text("not json at all", encoding="utf-8")
    assert Scheduler(path=bad2).pending() == []
