"""Composition root — the one place skills are named and wired together.

`build_orchestrator()` assembles the lifecycle: EchoEngine (keyless brain) +
a fresh ToolRegistry with the Spotify skill registered + a planner + an executor
with a confirmer. Keeping the registry local (not the global) avoids shared state
across tests. Adding a capability later means adding one `register_skill(...)`
line here and one skill file — never a `core/` edit.
"""

from __future__ import annotations

from core.executor import Executor
from core.orchestrator import Orchestrator
from core.planner import Planner
from engines.reasoning.providers.echo import EchoEngine
from skills.registry import ToolRegistry, register_skill
from skills.spotify.skill import SpotifySkill


def build_orchestrator(confirmer=None, spotify_client=None) -> Orchestrator:
    registry = ToolRegistry()
    register_skill(registry, SpotifySkill(client=spotify_client))

    engine = EchoEngine()
    planner = Planner(engine, registry)
    executor = Executor(registry, confirmer=confirmer)
    return Orchestrator(planner, executor)
