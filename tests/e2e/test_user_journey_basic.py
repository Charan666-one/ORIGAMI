"""C1 exit-criteria test — the play-music vertical slice, fully keyless.

Covers the three architecture guarantees:
  1. `origami "play some lofi"` runs end-to-end with no API keys (fake client).
  2. A CRITICAL tool refuses to run without explicit approval; runs with it.
  3. Adding a new tool touches zero `core/` files (registered at the edge).
"""

from __future__ import annotations

from core.executor import Executor
from core.schemas.goal import Goal
from core.schemas.plan import Plan, Step
from core.schemas.tool import Risk, ToolSpec
from main import build_orchestrator


class FakeSpotifyClient:
    """Stand-in for adapters.spotify.client.SpotifyClient — no network, no keys."""

    def __init__(self):
        self.last_query = None

    def search_and_play(self, query, track_type="track"):
        self.last_query = query
        return "Lofi Girl — beats to relax/study to"


# ---------------------------------------------------------------- slice works

async def test_play_music_runs_end_to_end_keyless():
    fake = FakeSpotifyClient()
    orchestrator = build_orchestrator(spotify_client=fake)

    result = await orchestrator.handle(Goal(text="play some lofi", source="cli"))

    assert result.success
    assert fake.last_query is not None and "lofi" in fake.last_query.lower()
    assert "Playing" in result.summary


async def test_unknown_goal_returns_graceful_summary():
    orchestrator = build_orchestrator(spotify_client=FakeSpotifyClient())
    result = await orchestrator.handle(Goal(text="defragment the toaster"))
    assert not result.steps
    assert "couldn't map" in result.summary.lower()


# ------------------------------------------------------------- risk gate (🔴)

async def test_critical_tool_refuses_without_approval():
    from skills.registry import ToolRegistry

    ran = {"called": False}
    reg = ToolRegistry()

    async def danger(**kwargs):
        ran["called"] = True
        return "boom"

    reg.register(ToolSpec(name="test.delete_everything",
                          description="destructive test tool", risk=Risk.CRITICAL),
                 danger)
    plan = Plan(goal=Goal(text="x"), steps=[Step(tool="test.delete_everything")])

    # default confirmer denies all consequences
    denied = await Executor(reg).run(plan)
    assert not ran["called"]
    assert denied.steps[0].skipped

    # explicit approval lets it run
    async def approve(spec, step):
        return True

    approved = await Executor(reg, confirmer=approve).run(plan)
    assert ran["called"]
    assert approved.steps[0].success


# -------------------------------------------- adding a tool needs no core edit

async def test_new_tool_registers_without_touching_core():
    from skills.registry import ToolRegistry

    reg = ToolRegistry()

    async def greet(**kwargs):
        return "hi"

    reg.register(ToolSpec(name="demo.greet", description="say hi",
                          risk=Risk.SAFE, keywords=("greet",)), greet)

    # the executor and registry handle a brand-new tool with zero core changes
    plan = Plan(goal=Goal(text="greet"), steps=[Step(tool="demo.greet")])
    result = await Executor(reg).run(plan)
    assert result.success and result.steps[0].output == "hi"
