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
from skills.desktop.skill import DesktopSkill
from skills.email.skill import EmailSkill
from skills.spotify.skill import SpotifySkill
from skills.terminal.skill import TerminalSkill
from skills.youtube.skill import YouTubeSkill


def build_orchestrator(confirmer=None, spotify_client=None, terminal_executor=None,
                       desktop_adapter=None) -> Orchestrator:
    registry = ToolRegistry()
    # Registration order = keyword-match priority. Terminal before Desktop so an
    # explicit "run ..." wins even if the command text contains "open".
    register_skill(registry, SpotifySkill(client=spotify_client))
    register_skill(registry, TerminalSkill(executor=terminal_executor))
    register_skill(registry, DesktopSkill(adapter=desktop_adapter))
    register_skill(registry, YouTubeSkill())
    register_skill(registry, EmailSkill())

    engine = EchoEngine()
    planner = Planner(engine, registry)
    executor = Executor(registry, confirmer=confirmer)
    return Orchestrator(planner, executor)
