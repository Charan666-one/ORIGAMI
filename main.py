"""Composition root — the one place skills are named and wired together.

`build_orchestrator()` assembles the lifecycle: a BrainManager (local Ollama →
Echo fallback, cloud optional) + a fresh ToolRegistry of skills + a planner +
an executor with a confirmer. Keeping the registry local (not the global) avoids
shared state across tests. Adding a capability = one `register_skill(...)` line
here plus one skill file — never a `core/` edit.
"""

from __future__ import annotations

import os

from core.executor import Executor
from core.orchestrator import Orchestrator
from core.planner import Planner
from engines.memory.engine import JSONMemory
from engines.memory.profile import UserProfile
from engines.planning.goals import GoalBook
from engines.planning.scheduler import Scheduler
from engines.reasoning.brain import BrainManager
from engines.reasoning.providers.ollama import OllamaProvider
from skills.registry import ToolRegistry, register_skill
from skills.assistant.skill import AssistantSkill
from skills.calendar.skill import CalendarSkill
from skills.desktop.skill import DesktopSkill
from skills.email.skill import EmailSkill
from skills.goals.skill import GoalsSkill
from skills.memory.skill import MemorySkill
from skills.profile.skill import ProfileSkill
from skills.reminder.skill import ReminderSkill
from skills.research.skill import ResearchSkill
from skills.spotify.skill import SpotifySkill
from skills.terminal.skill import TerminalSkill
from skills.youtube.skill import YouTubeSkill


def build_brain(cloud_consent=None, system_context="") -> BrainManager:
    """Assemble the brain: local Ollama first (offline-first), optional cloud, then
    Echo as the guaranteed keyless fallback. Providers that aren't available (server
    down, no key) are simply skipped by the manager. `system_context` (the user
    profile) is injected into every reasoning/generation call."""
    providers = [OllamaProvider()]

    cloud_name = os.getenv("ORIGAMI_CLOUD")  # e.g. "groq" — only if the user opts in
    if cloud_name:
        from engines.reasoning.providers.cloud import CloudProvider
        providers.append(CloudProvider(preset=cloud_name))

    return BrainManager(providers=providers, cloud_consent=cloud_consent,
                        system_context=system_context)


def build_orchestrator(confirmer=None, spotify_client=None, terminal_executor=None,
                       desktop_adapter=None, brain=None, cloud_consent=None,
                       memory=None, scheduler=None, goals=None) -> Orchestrator:
    profile = UserProfile()
    brain = brain or build_brain(cloud_consent=cloud_consent, system_context=profile.load())
    memory = memory if memory is not None else JSONMemory()
    scheduler = scheduler if scheduler is not None else Scheduler()
    goals = goals if goals is not None else GoalBook()

    registry = ToolRegistry()
    # Registration order = keyword-match priority (first keyword hit wins). Ordering
    # constraints: Goals before Reminder ("completed milestone" = goal step);
    # Reminder before Terminal ("remind me to run ..." must not hit terminal's
    # "run "); Terminal before Desktop ("run open X" = terminal); Assistant last
    # (conversational catch-all fallback).
    register_skill(registry, SpotifySkill(client=spotify_client))
    register_skill(registry, GoalsSkill(goals=goals, brain=brain))
    register_skill(registry, ReminderSkill(scheduler=scheduler))
    register_skill(registry, TerminalSkill(executor=terminal_executor))
    register_skill(registry, DesktopSkill(adapter=desktop_adapter))
    register_skill(registry, YouTubeSkill())
    register_skill(registry, CalendarSkill())
    register_skill(registry, ProfileSkill(profile=profile))
    register_skill(registry, ResearchSkill(brain=brain))
    register_skill(registry, MemorySkill(memory=memory))
    register_skill(registry, EmailSkill(brain=brain))
    register_skill(registry, AssistantSkill(brain=brain, memory=memory))

    planner = Planner(brain, registry)
    executor = Executor(registry, confirmer=confirmer)
    return Orchestrator(planner, executor)
