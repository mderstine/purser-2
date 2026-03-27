"""Low-level wrapper around the gh CLI.

All GitHub API interaction goes through `gh api` subprocess calls,
keeping auth consistent with the user's existing gh login.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from enum import Enum
from typing import Any


class GhAvailability(Enum):
    """Result of checking gh CLI availability."""

    AVAILABLE = "available"
    NOT_INSTALLED = "not_installed"
    NOT_AUTHENTICATED = "not_authenticated"


class GhCliError(Exception):
    """Raised when a gh CLI command fails."""

    def __init__(self, cmd: list[str], returncode: int, stderr: str) -> None:
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"gh command failed ({returncode}): {stderr}")


class GhNotAvailableError(Exception):
    """Raised when gh CLI is not available."""

    def __init__(self, status: GhAvailability) -> None:
        self.status = status
        if status == GhAvailability.NOT_INSTALLED:
            msg = "gh CLI not found. Install: https://cli.github.com/"
        else:
            msg = "gh CLI not authenticated. Run: gh auth login"
        super().__init__(msg)


def find_gh() -> str | None:
    """Find the gh binary on PATH."""
    return shutil.which("gh")


def detect_gh_cli() -> bool:
    """Check if the GitHub CLI (gh) is installed.

    Returns:
        True if gh CLI is found on PATH, False otherwise.
    """
    return shutil.which("gh") is not None


def verify_gh_auth() -> bool:
    """Check if gh CLI is authenticated with GitHub.

    Returns:
        True if gh CLI is installed and authenticated, False otherwise.
    """
    status = check_gh_availability()
    return status == GhAvailability.AVAILABLE


def detect_default_repo(cwd: str | None = None) -> str | None:
    """Detect the default GitHub repository from git remote.

    Parses the origin remote URL and returns it in 'owner/repo' format.
    Supports both HTTPS and SSH remote URLs.

    Args:
        cwd: Optional directory to run git command in (default: current directory).

    Returns:
        Owner/repo string (e.g., 'owner/repo') if a GitHub remote is found,
        None otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd,
        )
        if result.returncode != 0:
            return None

        remote_url = result.stdout.strip()

        # Parse HTTPS URL: https://github.com/owner/repo.git or https://github.com/owner/repo
        if remote_url.startswith("https://github.com/"):
            path = remote_url.replace("https://github.com/", "").rstrip("/")
            # Remove .git suffix if present
            if path.endswith(".git"):
                path = path[:-4]
            # Validate format (should be owner/repo)
            if "/" in path and path.count("/") == 1:
                return path

        # Parse SSH URL: git@github.com:owner/repo.git or git@github.com:owner/repo
        elif remote_url.startswith("git@github.com:"):
            path = remote_url.replace("git@github.com:", "")
            # Remove .git suffix if present
            if path.endswith(".git"):
                path = path[:-4]
            # Validate format (should be owner/repo)
            if "/" in path and path.count("/") == 1:
                return path

        return None
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return None


def check_gh_availability() -> GhAvailability:
    """Check if gh CLI is installed and authenticated."""
    gh_path = find_gh()
    if not gh_path:
        return GhAvailability.NOT_INSTALLED

    try:
        result = subprocess.run(
            [gh_path, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return GhAvailability.AVAILABLE
        return GhAvailability.NOT_AUTHENTICATED
    except (subprocess.TimeoutExpired, OSError):
        return GhAvailability.NOT_AUTHENTICATED


def get_gh_version() -> str | None:
    """Get gh CLI version string, or None if not installed."""
    gh_path = find_gh()
    if not gh_path:
        return None
    try:
        result = subprocess.run(
            [gh_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Output like: "gh version 2.40.1 (2024-01-01)"
            return result.stdout.strip().split("\n")[0]
        return None
    except (subprocess.TimeoutExpired, OSError):
        return None


def require_gh() -> str:
    """Return gh binary path, raising GhNotAvailableError if unavailable."""
    status = check_gh_availability()
    if status != GhAvailability.AVAILABLE:
        raise GhNotAvailableError(status)
    path = find_gh()
    assert path is not None  # guaranteed after availability check
    return path


def run_gh(
    args: list[str],
    *,
    json_output: bool = False,
    repo: str | None = None,
) -> dict[str, Any] | list[Any] | str:
    """Run a gh command and return output.

    Args:
        args: Command arguments (e.g., ["api", "/repos/{owner}/{repo}/issues"]).
        json_output: If True, parse output as JSON.
        repo: Optional repo override (owner/repo format).

    Returns:
        Parsed JSON (dict/list) if json_output=True, else raw stdout string.
    """
    gh_path = require_gh()
    cmd = [gh_path, *args]
    if repo and "--repo" not in args and "-R" not in args:
        cmd.extend(["--repo", repo])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise GhCliError(cmd, result.returncode, result.stderr.strip())

    if json_output:
        return json.loads(result.stdout)
    return result.stdout.strip()


def gh_api(
    endpoint: str,
    *,
    method: str = "GET",
    repo: str | None = None,
    fields: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    paginate: bool = False,
) -> dict[str, Any] | list[Any]:
    """Call the GitHub REST API via `gh api`.

    Args:
        endpoint: API endpoint (e.g., "/repos/{owner}/{repo}/issues").
        method: HTTP method (GET, POST, PATCH, DELETE).
        repo: Optional repo override.
        fields: Query parameters or form fields (-f key=value).
        json_body: JSON request body (--input -).
        paginate: Whether to paginate results.

    Returns:
        Parsed JSON response.
    """
    args = ["api", endpoint, "--method", method]
    if paginate:
        args.append("--paginate")

    if fields:
        for key, value in fields.items():
            args.extend(["-f", f"{key}={value}"])

    gh_path = require_gh()
    cmd = [gh_path, *args]
    if repo:
        cmd.extend(["--repo", repo])

    stdin_data = None
    if json_body is not None:
        cmd.extend(["--input", "-"])
        stdin_data = json.dumps(json_body)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=stdin_data,
        timeout=60,
    )

    if result.returncode != 0:
        raise GhCliError(cmd, result.returncode, result.stderr.strip())

    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def gh_graphql(
    query: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a GraphQL query via `gh api graphql`.

    Args:
        query: GraphQL query string.
        variables: Optional variables dict.

    Returns:
        The 'data' portion of the GraphQL response.
    """
    gh_path = require_gh()
    cmd = [gh_path, "api", "graphql", "-f", f"query={query}"]

    if variables:
        for key, value in variables.items():
            cmd.extend(
                ["-f", f"{key}={json.dumps(value) if not isinstance(value, str) else value}"]
            )

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise GhCliError(cmd, result.returncode, result.stderr.strip())

    response = json.loads(result.stdout)
    if "errors" in response:
        raise GhCliError(cmd, 1, json.dumps(response["errors"]))
    return response.get("data", response)
