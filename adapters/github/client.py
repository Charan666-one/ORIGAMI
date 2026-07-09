"""
adapters/github/client.py
GitHub REST API v3 client — repos, issues, PRs, commits, workflow triggers.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests
from requests import Response

from adapters.github.auth import GitHubAuth, GitHubAuthError

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubClientError(Exception):
    """Raised on any GitHub API error."""


class GitHubClient:
    """
    High-level GitHub API client for ORIGAMI.

    Usage:
        client = GitHubClient()
        repos = client.list_repos()
        issues = client.list_issues("owner", "repo")
    """

    def __init__(self, auth: Optional[GitHubAuth] = None, timeout: int = 15) -> None:
        self._auth = auth or GitHubAuth()
        self._timeout = timeout
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return self._auth.get_headers()

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        url = f"{GITHUB_API_BASE}{path}"
        resp = self._session.get(url, headers=self._headers(), params=params, timeout=self._timeout)
        self._raise_for_status(resp)
        return resp.json()

    def _post(self, path: str, body: dict) -> Any:
        url = f"{GITHUB_API_BASE}{path}"
        resp = self._session.post(url, headers=self._headers(), json=body, timeout=self._timeout)
        self._raise_for_status(resp)
        return resp.json() if resp.content else {}

    def _patch(self, path: str, body: dict) -> Any:
        url = f"{GITHUB_API_BASE}{path}"
        resp = self._session.patch(url, headers=self._headers(), json=body, timeout=self._timeout)
        self._raise_for_status(resp)
        return resp.json()

    def _delete(self, path: str) -> None:
        url = f"{GITHUB_API_BASE}{path}"
        resp = self._session.delete(url, headers=self._headers(), timeout=self._timeout)
        self._raise_for_status(resp)

    @staticmethod
    def _raise_for_status(resp: Response) -> None:
        if not resp.ok:
            try:
                message = resp.json().get("message", resp.text)
            except Exception:
                message = resp.text
            raise GitHubClientError(
                f"GitHub API error {resp.status_code}: {message}"
            )

    # ------------------------------------------------------------------
    # User / Auth
    # ------------------------------------------------------------------

    def get_authenticated_user(self) -> dict[str, Any]:
        """Return the authenticated user's profile."""
        return self._get("/user")

    # ------------------------------------------------------------------
    # Repositories
    # ------------------------------------------------------------------

    def list_repos(
        self,
        visibility: str = "all",
        sort: str = "updated",
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        """List repositories for the authenticated user."""
        return self._get(
            "/user/repos",
            params={"visibility": visibility, "sort": sort, "per_page": per_page},
        )

    def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        """Get repository metadata."""
        return self._get(f"/repos/{owner}/{repo}")

    def create_repo(
        self,
        name: str,
        description: str = "",
        private: bool = False,
        auto_init: bool = True,
    ) -> dict[str, Any]:
        """Create a new repository."""
        body = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init,
        }
        result = self._post("/user/repos", body)
        logger.info("Created repo %s.", name)
        return result

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------

    def list_issues(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        """List issues for a repository."""
        return self._get(
            f"/repos/{owner}/{repo}/issues",
            params={"state": state, "per_page": per_page},
        )

    def get_issue(self, owner: str, repo: str, issue_number: int) -> dict[str, Any]:
        """Get a single issue."""
        return self._get(f"/repos/{owner}/{repo}/issues/{issue_number}")

    def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str = "",
        labels: Optional[list[str]] = None,
        assignees: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Create a new issue."""
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        if assignees:
            payload["assignees"] = assignees
        result = self._post(f"/repos/{owner}/{repo}/issues", payload)
        logger.info("Created issue #%d in %s/%s.", result.get("number"), owner, repo)
        return result

    def close_issue(self, owner: str, repo: str, issue_number: int) -> dict[str, Any]:
        """Close an open issue."""
        return self._patch(
            f"/repos/{owner}/{repo}/issues/{issue_number}", {"state": "closed"}
        )

    def add_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> dict[str, Any]:
        """Add a comment to an issue or PR."""
        return self._post(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments", {"body": body}
        )

    # ------------------------------------------------------------------
    # Pull Requests
    # ------------------------------------------------------------------

    def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
    ) -> list[dict[str, Any]]:
        """List pull requests for a repository."""
        return self._get(
            f"/repos/{owner}/{repo}/pulls",
            params={"state": state, "per_page": per_page},
        )

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str = "",
        draft: bool = False,
    ) -> dict[str, Any]:
        """Open a new pull request."""
        payload = {
            "title": title,
            "head": head,
            "base": base,
            "body": body,
            "draft": draft,
        }
        result = self._post(f"/repos/{owner}/{repo}/pulls", payload)
        logger.info("Created PR #%d in %s/%s.", result.get("number"), owner, repo)
        return result

    # ------------------------------------------------------------------
    # Commits
    # ------------------------------------------------------------------

    def list_commits(
        self,
        owner: str,
        repo: str,
        branch: str = "main",
        per_page: int = 10,
    ) -> list[dict[str, Any]]:
        """List recent commits on a branch."""
        return self._get(
            f"/repos/{owner}/{repo}/commits",
            params={"sha": branch, "per_page": per_page},
        )

    def get_commit(self, owner: str, repo: str, sha: str) -> dict[str, Any]:
        """Get details of a specific commit."""
        return self._get(f"/repos/{owner}/{repo}/commits/{sha}")

    # ------------------------------------------------------------------
    # GitHub Actions / Workflows
    # ------------------------------------------------------------------

    def list_workflows(self, owner: str, repo: str) -> list[dict[str, Any]]:
        """List all workflows in a repository."""
        result = self._get(f"/repos/{owner}/{repo}/actions/workflows")
        return result.get("workflows", [])

    def trigger_workflow(
        self,
        owner: str,
        repo: str,
        workflow_id: str,
        ref: str = "main",
        inputs: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Trigger a workflow dispatch event.

        Args:
            workflow_id: Workflow file name (e.g. 'deploy.yml') or numeric ID.
            ref: Git ref (branch/tag) to run the workflow on.
            inputs: Optional key-value inputs for the workflow.
        """
        payload: dict[str, Any] = {"ref": ref}
        if inputs:
            payload["inputs"] = inputs
        self._post(
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches", payload
        )
        logger.info("Triggered workflow %s on %s/%s@%s.", workflow_id, owner, repo, ref)

    def list_workflow_runs(
        self,
        owner: str,
        repo: str,
        workflow_id: str,
        per_page: int = 10,
    ) -> list[dict[str, Any]]:
        """Return recent runs for a specific workflow."""
        result = self._get(
            f"/repos/{owner}/{repo}/actions/workflows/{workflow_id}/runs",
            params={"per_page": per_page},
        )
        return result.get("workflow_runs", [])

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_repos(self, query: str, per_page: int = 10) -> list[dict[str, Any]]:
        """Search GitHub repositories by query string."""
        result = self._get("/search/repositories", params={"q": query, "per_page": per_page})
        return result.get("items", [])

    def search_code(
        self, query: str, owner: str, repo: str, per_page: int = 10
    ) -> list[dict[str, Any]]:
        """Search code within a specific repository."""
        result = self._get(
            "/search/code",
            params={"q": f"{query} repo:{owner}/{repo}", "per_page": per_page},
        )
        return result.get("items", [])