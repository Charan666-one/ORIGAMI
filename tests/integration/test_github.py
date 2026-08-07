"""GitHub skill — reads, issue creation, routing (mocked client, no network)."""

from __future__ import annotations

from core.schemas.goal import Goal
from engines.reasoning.llm import LLMEngine, LLMResponse, Task
from main import build_orchestrator
from skills.github.skill import GitHubSkill


class FakeGitHub:
    def __init__(self):
        self.created = None

    def get_authenticated_user(self):
        return {"login": "charan", "name": "Charan", "public_repos": 12, "followers": 5}

    def list_repos(self):
        return [{"full_name": "charan/ORIGAMI", "language": "Python", "stargazers_count": 3}]

    def list_issues(self, owner, repo):
        return [{"number": 7, "title": "Fix the login bug"}]

    def list_pull_requests(self, owner, repo):
        return [{"number": 2, "title": "Add search"}]

    def search_repos(self, query, per_page=10):
        return [{"full_name": "psf/requests", "stargazers_count": 50000, "description": "HTTP"}]

    def create_issue(self, owner, repo, title):
        self.created = (owner, repo, title)
        return {"number": 9}


async def test_list_repos():
    out = await GitHubSkill(client=FakeGitHub()).execute("github.repos")
    assert "charan/ORIGAMI" in out


async def test_issues_resolve_explicit_repo():
    out = await GitHubSkill(client=FakeGitHub()).execute(
        "github.issues", _raw="issues in charan/ORIGAMI")
    assert "#7 Fix the login bug" in out


async def test_issues_bare_repo_uses_my_login():
    out = await GitHubSkill(client=FakeGitHub()).execute("github.issues", _raw="issues in ORIGAMI")
    assert "charan/ORIGAMI" in out


async def test_create_issue():
    fake = FakeGitHub()
    out = await GitHubSkill(client=fake).execute(
        "github.create_issue", _raw="create an issue in charan/ORIGAMI: fix the crash")
    assert fake.created == ("charan", "ORIGAMI", "fix the crash")
    assert "#9" in out


async def test_search_github():
    out = await GitHubSkill(client=FakeGitHub()).execute("github.search", query="requests")
    assert "psf/requests" in out


async def test_no_token_is_graceful():
    class NoAuth(FakeGitHub):
        def list_repos(self):
            raise RuntimeError("GitHub auth not configured")
    out = await GitHubSkill(client=NoAuth()).execute("github.repos")
    assert "GITHUB_TOKEN" in out


async def test_github_routing():
    orch = build_orchestrator()
    for text, expected in {
        "my repos": "github.repos",
        "check all the repo i have in github": "github.repos",
        "my pull requests": "github.prs",
        "create an issue in a/b: hi": "github.create_issue",
        "search github for fastapi": "github.search",
        "my github profile": "github.me",
        "what's the best project i have on github": "github.analyze",
        "what are my java projects on github": "github.analyze",
        "which of my repos should i polish": "github.analyze",
    }.items():
        plan = await orch.planner.plan(Goal(text=text))
        assert plan.steps[0].tool == expected, f"{text!r} -> {plan.steps[0].tool}"


class _AnalyzeBrain(LLMEngine):
    def can_think(self):
        return True

    async def complete(self, prompt, task=Task.REASON, **kwargs):
        # sees the repo table -> "answers" by echoing a repo it saw
        return LLMResponse(text="Your strongest is ORIGAMI (Python).")


async def test_analyze_uses_brain_over_repo_data():
    from engines.reasoning.llm import LLMEngine as _LE  # noqa
    skill = GitHubSkill(client=FakeGitHub(), brain=_AnalyzeBrain())
    out = await skill.execute("github.analyze", _raw="what's my best project")
    assert "ORIGAMI" in out


async def test_analyze_without_model_is_graceful():
    skill = GitHubSkill(client=FakeGitHub(), brain=None)
    out = await skill.execute("github.analyze", _raw="best project")
    assert "ollama" in out.lower()
