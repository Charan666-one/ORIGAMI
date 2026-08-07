"""FastAPI surface — serves the ORIGAMI dashboard and its live state.

This is a *surface* (Layer 1): it owns no logic, it renders what the engines
already know. The JSON contract in `/api/state` is stable, so the UI can be
replaced (Next.js, mobile, voice) without touching ORIGAMI.

    origami dashboard          # or: uvicorn interfaces.api.app:app --reload
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from core.schemas.goal import Goal
from interfaces.api.state import build_state

app = FastAPI(title="ORIGAMI", docs_url="/api/docs")

_DASHBOARD = Path(__file__).parent / "dashboard.html"
_orchestrator = None
_health: Dict[str, Any] = {}
_lock = threading.Lock()


def orchestrator():
    """Built once, lazily — starting the server must not require a model."""
    global _orchestrator
    with _lock:
        if _orchestrator is None:
            from main import build_orchestrator
            _orchestrator = build_orchestrator(confirmer=_auto_deny)
    return _orchestrator


async def _auto_deny(spec, step) -> bool:
    """The dashboard never auto-approves consequences (CONFIRM/CRITICAL)."""
    return False


def _refresh_health() -> None:
    """Health analysis is ~1s, so cache it in the background."""
    global _health
    try:
        from engines.health.engine import ProjectHealthEngine
        engine = ProjectHealthEngine()
        report = engine.run()
        _health = {
            "overall": report.overall,
            "scores": report.scores,
            "criticals": [f.message for f in report.by_severity("critical")][:4],
            "warnings": [f.message for f in report.by_severity("warning")][:5],
            "recommendations": report.recommendations()[:4],
            "capabilities": [
                {"name": c.name, "score": c.score, "tools": c.tools}
                for c in report.capabilities
            ],
            "checked_at": time.time(),
        }
    except Exception as exc:  # never break the dashboard over analysis
        _health = {"overall": 0, "scores": {}, "error": str(exc)}


@app.on_event("startup")
async def _startup() -> None:
    threading.Thread(target=_refresh_health, daemon=True).start()


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    return _DASHBOARD.read_text(encoding="utf-8")


@app.get("/api/state")
async def state() -> JSONResponse:
    data = await asyncio.to_thread(build_state, orchestrator(), _health)
    return JSONResponse(data)


@app.post("/api/health/refresh")
async def refresh_health() -> JSONResponse:
    await asyncio.to_thread(_refresh_health)
    return JSONResponse(_health)


class Command(BaseModel):
    text: str


@app.post("/api/command")
async def command(cmd: Command) -> JSONResponse:
    """Run a goal through the real orchestrator (consequences stay gated)."""
    text = (cmd.text or "").strip()
    if not text:
        return JSONResponse({"summary": "Say something.", "tool": None})
    result = await orchestrator().handle(Goal(text=text, source="dashboard"))
    return JSONResponse({
        "summary": result.summary,
        "tool": result.steps[0].step.tool if result.steps else None,
        "learned": result.learned,
        "success": result.success,
    })
