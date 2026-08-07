"""GitHubSkill — read and act on your GitHub. Wraps the existing GitHub adapter.

Reads (repos/issues/PRs/search) are SAFE; creating an issue is CONFIRM (a write).
Needs a free Personal Access Token in the environment: GITHUB_TOKEN. The client is
created lazily so building the app never requires the token.
"""

from __future__ import annotations

import re
from typing import Any, List

from core.schemas.tool import Risk, ToolSpec
from skills.base import Skill

# owner/repo or a bare repo name in the text
_REPO = re.compile(r"\b([\w.-]+/[\w.-]+)\b")
_BARE = re.compile(r"\b(?:in|for|on|repo)\s+([\w.-]{2,})", re.IGNORECASE)


class GitHubSkill(Skill):
    def __init__(self, client: Any = None) -> None:
        self._client = client
        self._me = None

    @property
    def client(self):
        if self._client is None:
            from adapters.github.client import GitHubClient  # lazy import
            self._client = GitHubClient()
        return self._client

    def specs(self) -> List[ToolSpec]:
        return [
            ToolSpec(name="github.repos", description="List your GitHub repositories.",
                     risk=Risk.SAFE,
                     keywords=("my repos", "my repositories", "repositories", "list my repos",
                               "my github repos", "list repos", "github repos", "active repos",
                               "repos in github", "repositories in github")),
            ToolSpec(name="github.prs", description="List open pull requests in a repo.",
                     params={"repo": "owner/repo"}, risk=Risk.SAFE,
                     keywords=("my pull requests", "my prs", "pull requests", "list prs",
                               "open prs")),
            ToolSpec(name="github.create_issue",
                     description="Create an issue in a repo.",
                     params={"text": "repo and issue title"}, risk=Risk.CONFIRM,
                     keywords=("create an issue", "open an issue", "new issue",
                               "file an issue", "raise an issue")),
            ToolSpec(name="github.issues", description="List open issues in a repo.",
                     params={"repo": "owner/repo"}, risk=Risk.SAFE,
                     keywords=("my issues", "list issues", "github issues", "open issues",
                               "issues in")),
            ToolSpec(name="github.search", description="Search GitHub repositories.",
                     params={"query": "what to search"}, risk=Risk.SAFE,
                     keywords=("search github", "search repos", "find a repo",
                               "github search")),
            ToolSpec(name="github.me", description="Your GitHub profile summary.",
                     risk=Risk.SAFE,
                     keywords=("my github", "github profile", "who am i on github")),
        ]

    async def execute(self, tool: str, **kwargs) -> Any:
        try:
            return self._dispatch(tool, kwargs)
        except Exception as exc:
            msg = str(exc)
            if "not configured" in msg or "401" in msg:
                return ("GitHub isn't connected. Create a free token at "
                        "github.com/settings/tokens and add GITHUB_TOKEN=... to .env.")
            return f"GitHub error: {msg}"

    def _dispatch(self, tool: str, kwargs: dict) -> str:
        raw = kwargs.get("_raw") or ""
        if tool == "github.me":
            u = self.client.get_authenticated_user()
            return (f"👤 {u.get('login')} — {u.get('name', '')}\n"
                    f"repos: {u.get('public_repos', 0)} · followers: {u.get('followers', 0)}")
        if tool == "github.repos":
            repos = self.client.list_repos()
            if not repos:
                return "No repositories found."
            lines = [f"📦 {r.get('full_name')}  ({r.get('language') or '—'}, "
                     f"★{r.get('stargazers_count', 0)})" for r in repos[:15]]
            return "Your repos:\n" + "\n".join(lines)
        if tool == "github.search":
            query = (kwargs.get("query") or raw).strip()
            results = self.client.search_repos(query, per_page=8)
            if not results:
                return f"No repos found for '{query}'."
            return "🔎 " + query + ":\n" + "\n".join(
                f"- {r.get('full_name')} ★{r.get('stargazers_count', 0)}: "
                f"{(r.get('description') or '')[:70]}" for r in results)

        owner, repo = self._resolve_repo(raw)
        if tool in ("github.issues", "github.prs") and not repo:
            return "Which repo? e.g. 'issues in owner/repo' or 'issues in my-repo'."

        if tool == "github.issues":
            issues = self.client.list_issues(owner, repo)
            if not issues:
                return f"No open issues in {owner}/{repo}."
            return f"🐛 {owner}/{repo} issues:\n" + "\n".join(
                f"- #{i.get('number')} {i.get('title')}" for i in issues[:15])
        if tool == "github.prs":
            prs = self.client.list_pull_requests(owner, repo)
            if not prs:
                return f"No open PRs in {owner}/{repo}."
            return f"🔀 {owner}/{repo} PRs:\n" + "\n".join(
                f"- #{p.get('number')} {p.get('title')}" for p in prs[:15])
        if tool == "github.create_issue":
            if not repo:
                return "Which repo and title? e.g. 'create an issue in owner/repo: fix login'."
            title = self._issue_title(raw)
            if not title:
                return "What's the issue title? e.g. 'create an issue in owner/repo: <title>'."
            created = self.client.create_issue(owner, repo, title)
            return f"✅ Created issue #{created.get('number')} in {owner}/{repo}: {title}"
        raise ValueError(f"Unknown tool: {tool}")

    # ------------------------------------------------------------------ helpers

    def _resolve_repo(self, text: str):
        m = _REPO.search(text)
        if m:
            owner, repo = m.group(1).split("/", 1)
            return owner, repo
        m = _BARE.search(text)
        if m:
            return self._my_login(), m.group(1)
        return None, None

    def _my_login(self) -> str:
        if self._me is None:
            try:
                self._me = self.client.get_authenticated_user().get("login", "")
            except Exception:
                self._me = ""
        return self._me

    @staticmethod
    def _issue_title(text: str) -> str:
        if ":" in text:
            return text.split(":", 1)[1].strip()
        # after "titled"/"about"/"for"
        m = re.search(r"\b(?:titled|about|saying)\s+(.+)$", text, re.IGNORECASE)
        return m.group(1).strip() if m else ""
