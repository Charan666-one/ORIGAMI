"""Project launcher — start/open/list local projects (mocked launcher)."""

from __future__ import annotations

from core.schemas.goal import Goal
from main import build_orchestrator
from skills.projects.skill import ProjectsSkill


class FakeLauncher:
    def __init__(self):
        self.folders, self.editors, self.terminals = [], [], []

    def open_folder(self, path):
        self.folders.append(path)

    def open_editor(self, path):
        self.editors.append(path)

    def run_terminal(self, path, cmd):
        self.terminals.append((path, cmd))


def _skill(tmp_path, launcher):
    cfg = tmp_path / "projects.json"
    cfg.write_text(
        '{"careerlens": {"path": "' + str(tmp_path) + '", "run": ["cmd1", "cmd2"], '
        '"editor": true}}', encoding="utf-8")
    return ProjectsSkill(config_path=cfg, launcher=launcher)


async def test_start_runs_dev_commands(tmp_path):
    fake = FakeLauncher()
    skill = _skill(tmp_path, fake)
    msg = await skill.execute("project.control", _raw="start careerlens")
    assert "Started careerlens" in msg
    assert fake.folders and fake.editors                 # opened folder + editor
    assert [c for _, c in fake.terminals] == ["cmd1", "cmd2"]  # ran both dev cmds


async def test_open_only_does_not_run_commands(tmp_path):
    fake = FakeLauncher()
    skill = _skill(tmp_path, fake)
    msg = await skill.execute("project.control", _raw="open careerlens")
    assert "Opened careerlens" in msg
    assert fake.folders and not fake.terminals           # no dev processes started


async def test_list_projects(tmp_path):
    skill = _skill(tmp_path, FakeLauncher())
    msg = await skill.execute("project.control", _raw="my projects")
    assert "careerlens" in msg


async def test_unknown_project(tmp_path):
    skill = _skill(tmp_path, FakeLauncher())
    msg = await skill.execute("project.control", _raw="start nonexistent")
    assert "Which project" in msg


async def test_project_routing():
    orch = build_orchestrator()
    for text, is_project in {
        "start careerlens": True,
        "open wavex": True,
        "my projects": True,
        "open Safari": False,          # a real app, not a project
    }.items():
        plan = await orch.planner.plan(Goal(text=text))
        tool = plan.steps[0].tool if plan.steps else ""
        assert (tool == "project.control") == is_project, f"{text!r} -> {tool}"
