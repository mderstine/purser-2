"""Multi-repo support for GitHub integration.

Routes beads to appropriate repositories based on labels.
"""

from __future__ import annotations

from purser.models import GitHubConfig, Issue  # noqa: TC001


def get_target_repo(issue: Issue, gh_config: GitHubConfig) -> str | None:
    """Determine which repository a bead should be synced to.

    Rules:
    1. If no multi-repo config, use default repo
    2. If bead labels match a repo's labels, use that repo
    3. Otherwise, use default repo

    Returns owner/repo string or None if no repo configured.
    """
    default_repo = gh_config.repo
    multi_repos = gh_config.repos

    if not multi_repos:
        return default_repo

    # Check if any bead labels match repo labels
    for repo_config in multi_repos:
        if any(label in issue.labels for label in repo_config.labels):
            return repo_config.name

    # Fall back to default repo
    return default_repo


def get_all_repos(gh_config: GitHubConfig) -> list[str]:
    """Get all configured repository names (default + multi-repo)."""
    repos = []
    if gh_config.repo:
        repos.append(gh_config.repo)
    for repo_config in gh_config.repos:
        if repo_config.name not in repos:
            repos.append(repo_config.name)
    return repos


def group_issues_by_repo(
    issues: list[Issue], gh_config: GitHubConfig
) -> dict[str, list[Issue]]:
    """Group issues by their target repository.

    Returns dict mapping repo name -> list of issues.
    """
    groups: dict[str, list[Issue]] = {}

    for issue in issues:
        repo = get_target_repo(issue, gh_config)
        if repo:
            if repo not in groups:
                groups[repo] = []
            groups[repo].append(issue)

    return groups
