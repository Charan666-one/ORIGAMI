"""Dashboard state — one snapshot of everything ORIGAMI knows about itself.

This is the stable contract the UI renders. Any surface (this dashboard, a future
Next.js app, mobile, voice) reads the same shape, so the UI can be replaced
without touching ORIGAMI. New capabilities appear here automatically because the
list is built from the live registry.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List

from engines.knowledge.codebases import CodebaseStore
from engines.memory.engine import JSONMemory
from engines.memory.profile import UserProfile
from engines.planning.goals import GoalBook
from engines.planning.scheduler import Scheduler


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


def build_state(orchestrator=None, health_cache: Dict[str, Any] | None = None) -> Dict[str, Any]:
    scheduler = _safe(Scheduler, None)
    goals = _safe(GoalBook, None)
    memory = _safe(JSONMemory, None)
    codebases = _safe(CodebaseStore, None)
    profile = _safe(UserProfile, None)

    now = datetime.now()
    state: Dict[str, Any] = {
        "time": now.strftime("%I:%M").lstrip("0"),
        "meridiem": now.strftime("%p"),
        "date": now.strftime("%A, %B %d, %Y"),
        "greeting": _greeting(now.hour),
        "user": _first_name(profile),
        "generated_at": time.time(),
    }

    # --- Monitoring Engine ---------------------------------------------------
    pending = _safe(lambda: scheduler.pending(), []) if scheduler else []
    state["monitoring"] = {
        "streak": _safe(lambda: scheduler.streak, 0) if scheduler else 0,
        "pending": len(pending),
        "focus": [
            {
                "text": t.text,
                "due": datetime.fromtimestamp(t.due).strftime("%a %I:%M %p").lstrip("0"),
                "overdue": t.due < time.time(),
                "important": bool(getattr(t, "important", False)),
            }
            for t in pending[:6]
        ],
        "week": _week_dots(scheduler),
    }

    # --- Executive / Goals ---------------------------------------------------
    active = _safe(lambda: goals.active(), []) if goals else []
    goal_rows = []
    for g in active[:5]:
        done, total = g.progress()
        nxt = g.next_open()
        goal_rows.append({
            "title": g.title,
            "percent": round(100 * done / total) if total else 0,
            "done": done, "total": total,
            "next": nxt[0].text if nxt else "complete",
        })
    state["goals"] = goal_rows

    # --- Memory Engine -------------------------------------------------------
    records = _safe(lambda: memory.all(), []) if memory else []
    state["memory"] = {
        "count": len(records),
        "important": sum(1 for r in records if getattr(r, "kind", "") == "important"),
        "recent": [
            {"text": r.text[:90], "kind": getattr(r, "kind", "fact"),
             "when": _ago(getattr(r, "created_at", time.time()))}
            for r in sorted(records, key=lambda r: getattr(r, "created_at", 0),
                            reverse=True)[:6]
        ],
    }

    # --- Codex / codebases ---------------------------------------------------
    cb = _safe(lambda: codebases.all(), {}) if codebases else {}
    state["codebases"] = [
        {
            "name": name,
            "languages": list((data.get("languages") or {}).keys())[:3],
            "files": data.get("total_files", 0),
            "summary": (data.get("summary") or "")[:150],
        }
        for name, data in list(cb.items())[:6]
    ]

    # --- Brain Manager -------------------------------------------------------
    state["brain"] = _brain_state(orchestrator)

    # --- Capability Registry (auto-populated: future modules appear here) ----
    state["capabilities"] = _capabilities(orchestrator)

    # --- Project Health Engine ----------------------------------------------
    state["health"] = health_cache or {}

    # --- System vitals (CPU / memory / storage / network) -------------------
    state["system"] = _system()

    # --- Active projects (launcher config + goals + scanned codebases) -------
    state["projects"] = _projects(cb, goal_rows)

    # --- Upcoming events (reminders as dated chips) -------------------------
    state["events"] = [
        {
            "day": datetime.fromtimestamp(t.due).strftime("%d"),
            "month": datetime.fromtimestamp(t.due).strftime("%b").upper(),
            "title": t.text,
            "when": _relative_day(t.due),
            "important": bool(getattr(t, "important", False)),
        }
        for t in pending[:5]
    ]

    # --- Now playing (best-effort; silent without Spotify credentials) -------
    state["now_playing"] = _now_playing()

    # --- Authentication Engine ----------------------------------------------
    state["auth"] = _auth()

    return state


def _auth() -> Dict[str, Any]:
    """Identity status for the dashboard (never exposes the embedding)."""
    try:
        from engines.auth.engine import AuthenticationEngine
        s = AuthenticationEngine().status()
        return {"enrolled": s["enrolled"], "user": s["user"],
                "wake_phrase": s["wake_phrase"], "verifier": s["verifier"],
                "session": s["session"], "locked_out": s["locked_out"],
                "methods": [m["name"] for m in s["methods"] if m["available"]],
                "confidence": s["session"]["confidence"]}
    except Exception:
        return {"enrolled": False, "session": {"active": False}, "methods": []}


def _system() -> Dict[str, Any]:
    out = {"cpu": None, "memory": None, "storage": None, "network": 98}
    try:
        import psutil
        out["cpu"] = round(psutil.cpu_percent(interval=0.05))
        out["memory"] = round(psutil.virtual_memory().percent)
        out["storage"] = round(psutil.disk_usage("/").percent)
    except Exception:
        pass
    return out


def _projects(codebases: Dict[str, Any], goals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Everything ORIGAMI is tracking as work-in-progress."""
    import json
    rows: List[Dict[str, Any]] = []
    for g in goals[:3]:
        rows.append({"name": g["title"][:28], "percent": g["percent"], "kind": "goal"})

    cfg = _safe(lambda: json.loads(
        (UserProfile().path.parent / "projects.json").read_text(encoding="utf-8")), {})
    for name in list(cfg)[:4]:
        if len(rows) >= 5:
            break
        scanned = name.lower() in {k.lower() for k in codebases}
        rows.append({"name": name, "percent": 100 if scanned else 40,
                     "kind": "scanned" if scanned else "project"})
    return rows


def _relative_day(ts: float) -> str:
    delta = ts - time.time()
    if delta < 0:
        return "overdue"
    if delta < 86400:
        return datetime.fromtimestamp(ts).strftime("Today, %I:%M %p").lstrip("0")
    days = int(delta // 86400) + 1
    return f"In {days} days" if days > 1 else "Tomorrow"


def _now_playing() -> Dict[str, Any]:
    import os
    if not (os.getenv("SPOTIFY_CLIENT_ID") and os.getenv("SPOTIFY_CLIENT_SECRET")):
        return {"active": False}
    try:
        from adapters.spotify.client import SpotifyClient
        track = SpotifyClient().get_current_track()
        if not track:
            return {"active": False}
        return {
            "active": True,
            "title": track.get("name", "—"),
            "artist": ", ".join(a["name"] for a in track.get("artists", []))[:40],
            "art": (track.get("album", {}).get("images") or [{}])[-1].get("url", ""),
        }
    except Exception:
        return {"active": False}


def _greeting(hour: int) -> str:
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def _first_name(profile) -> str:
    """Preferred name from the profile header: '# USER PROFILE — P. Sri Sai Charan (…)'."""
    text = _safe(lambda: profile.load(), "") if profile else ""
    for line in text.splitlines():
        if "—" in line and "USER PROFILE" in line.upper():
            name = line.split("—", 1)[1].split("(")[0].strip(" *#")
            if name:
                return name.split()[-1]  # the name they go by
    return "Charan"


def _week_dots(scheduler) -> List[bool]:
    """Completion dots for the last 7 days (done tasks per day)."""
    if scheduler is None:
        return [False] * 7
    tasks = _safe(lambda: scheduler.all(), [])
    today = datetime.now().date()
    dots = []
    for offset in range(6, -1, -1):
        day = today.fromordinal(today.toordinal() - offset)
        dots.append(any(
            t.status == "done" and
            datetime.fromtimestamp(getattr(t, "due", 0)).date() == day
            for t in tasks))
    return dots


def _ago(ts: float) -> str:
    delta = max(0, time.time() - ts)
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


def _brain_state(orchestrator) -> Dict[str, Any]:
    brain = getattr(getattr(orchestrator, "planner", None), "engine", None)
    if brain is None:
        return {"online": False, "provider": "—", "model": "—", "mode": "offline"}
    try:
        online = brain.can_think()
        provider = brain.active_model()
        model = "—"
        for p in getattr(brain, "providers", []):
            if hasattr(p, "model_for") and p.is_available():
                from engines.reasoning.llm import Task
                model = p.model_for(Task.REASON) or "—"
                break
        res = getattr(brain, "resources", None)
        snap = res.snapshot() if res else None
        return {
            "online": bool(online),
            "provider": provider,
            "model": model,
            "mode": "local · offline-first" if online else "echo (no model)",
            "ram_free": getattr(snap, "ram_available_gb", None),
            "cpu": getattr(snap, "cpu_percent", None),
            "battery": getattr(snap, "battery_percent", None),
        }
    except Exception:
        return {"online": False, "provider": "—", "model": "—", "mode": "unknown"}


def _capabilities(orchestrator) -> List[Dict[str, Any]]:
    """Straight from the live registry — new capabilities appear automatically."""
    registry = getattr(getattr(orchestrator, "executor", None), "registry", None)
    if registry is None:
        return []
    groups: Dict[str, Dict[str, Any]] = {}
    for spec in _safe(lambda: registry.all(), []):
        family = spec.name.split(".", 1)[0]
        entry = groups.setdefault(family, {"name": family, "tools": 0, "risk": "safe"})
        entry["tools"] += 1
        if getattr(spec.risk, "value", "safe") != "safe":
            entry["risk"] = spec.risk.value
    return sorted(groups.values(), key=lambda g: -g["tools"])
