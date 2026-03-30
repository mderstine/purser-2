"""CLI commands for GitHub integration (purser gh ...)."""

from __future__ import annotations

from pathlib import Path

import click

from purser.gh.cli import check_gh_availability, get_gh_version
from purser.models import GitHubConfig


def _get_sync_store():
    """Get or create the SyncStore for the current project."""
    from purser.gh.sync_store import SyncStore

    db_path = Path(".purser/gh_sync.duckdb")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return SyncStore(db_path)


def _require_gh_config():
    """Load config and verify GH integration is enabled."""
    from purser.config import load_config

    config = load_config()
    if not config.github.enabled:
        click.echo("GitHub integration is not enabled.", err=True)
        click.echo("Enable it in purser.toml:", err=True)
        click.echo("  [github]", err=True)
        click.echo("  enabled = true", err=True)
        click.echo('  repo = "owner/repo"', err=True)
        raise SystemExit(1)
    return config


def write_github_config(
    repo: str,
    project: str | None = None,
    *,
    config_path: Path | None = None,
) -> Path:
    """Write the [github] section in purser.toml for the current project."""
    GitHubConfig(enabled=True, repo=repo, project=project)

    target = config_path or Path("purser.toml")
    content = target.read_text() if target.exists() else ""

    import re

    content = re.sub(r"\[github\].*?(?=\n\[|\Z)", "", content, flags=re.DOTALL).rstrip()

    gh_section = f'\n\n[github]\nenabled = true\nrepo = "{repo}"\n'
    if project:
        gh_section += f'project = "{project}"\n'
    gh_section += 'conflict_strategy = "local-wins"\n'

    target.write_text(content + gh_section)
    return target


@click.group("gh")
def gh_group() -> None:
    """GitHub integration commands."""


@gh_group.command("attach")
@click.option("--repo", "-r", default=None, help="GitHub repo (owner/repo)")
@click.option("--project", "-p", default=None, help="GitHub Project name or number")
def gh_attach(repo: str | None, project: str | None) -> None:
    """Configure GitHub repo and project for this purser instance.

    Detects gh CLI, prompts for repo/project if not provided, validates,
    and writes [github] section to purser.toml.
    """
    from purser.gh.cli import GhAvailability

    # Check gh CLI
    gh_avail = check_gh_availability()
    if gh_avail == GhAvailability.NOT_INSTALLED:
        click.echo("Error: gh CLI not installed. Install: https://cli.github.com/", err=True)
        raise SystemExit(1)
    if gh_avail == GhAvailability.NOT_AUTHENTICATED:
        click.echo("Error: gh CLI not authenticated. Run: gh auth login", err=True)
        raise SystemExit(1)

    click.echo(f"gh CLI: {get_gh_version()}")

    # Get repo
    if not repo:
        # Try to detect from git remote
        import subprocess

        try:
            result = subprocess.run(
                ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                default_repo = result.stdout.strip()
                repo = click.prompt("GitHub repo", default=default_repo)
            else:
                repo = click.prompt("GitHub repo (owner/repo)")
        except Exception:
            repo = click.prompt("GitHub repo (owner/repo)")

    if not project:
        project = click.prompt("GitHub Project (name or number, leave empty to skip)", default="")
        if not project:
            project = None

    config_path = write_github_config(repo, project)

    click.echo(f"\nGitHub integration configured in {config_path}:")
    click.echo(f"  repo = {repo}")
    if project:
        click.echo(f"  project = {project}")
    click.echo("\nNext: purser gh sync")


@gh_group.command("status")
def gh_status() -> None:
    """Show GitHub sync status."""
    from purser.config import load_config

    config = load_config()

    # GH CLI status
    gh_avail = check_gh_availability()
    gh_ver = get_gh_version()
    click.echo(f"  gh CLI: {gh_avail.value}" + (f" ({gh_ver})" if gh_ver else ""))

    # Config status
    click.echo(f"  GitHub integration: {'enabled' if config.github.enabled else 'disabled'}")
    if config.github.repo:
        click.echo(f"  Repository: {config.github.repo}")
    if config.github.project:
        click.echo(f"  Project: {config.github.project}")
    click.echo(f"  Conflict strategy: {config.github.conflict_strategy}")

    # Sync state
    db_path = Path(".purser/gh_sync.duckdb")
    if db_path.exists():
        store = _get_sync_store()
        summary = store.summary()
        last_sync = store.last_sync_time()
        total = sum(summary.values())

        click.echo()
        click.echo(f"  Linked beads: {total}")
        for status, count in sorted(summary.items()):
            click.echo(f"    {status}: {count}")

        if last_sync:
            click.echo(f"  Last sync: {last_sync.isoformat()}")
        else:
            click.echo("  Last sync: never")
        store.close()
    else:
        click.echo()
        click.echo("  No sync state found. Run 'purser gh sync' to start.")


@gh_group.command("link")
@click.argument("bead_id")
@click.argument("gh_issue", type=int)
def gh_link(bead_id: str, gh_issue: int) -> None:
    """Link a local bead to an existing GitHub issue.

    Example: purser gh link bd-42 123
    """
    config = _require_gh_config()

    from purser.gh.sync_store import SyncState

    store = _get_sync_store()

    existing = store.get(bead_id)
    if existing and existing.gh_issue_num:
        click.echo(
            f"Bead {bead_id} is already linked to #{existing.gh_issue_num} in {existing.gh_repo}",
            err=True,
        )
        click.echo("Use 'purser gh unlink' first to remove the existing link.", err=True)
        raise SystemExit(1)

    repo = config.github.repo or ""
    state = SyncState(
        bead_id=bead_id,
        gh_repo=repo,
        gh_issue_num=gh_issue,
        sync_status="unlinked",
    )
    store.upsert(state)
    store.close()
    click.echo(f"Linked {bead_id} → {repo}#{gh_issue}")


@gh_group.command("unlink")
@click.argument("bead_id")
def gh_unlink(bead_id: str) -> None:
    """Remove GitHub link from a local bead.

    Example: purser gh unlink bd-42
    """
    store = _get_sync_store()
    existing = store.get(bead_id)
    if not existing:
        click.echo(f"Bead {bead_id} is not linked to any GitHub issue.", err=True)
        raise SystemExit(1)

    store.delete(bead_id)
    store.close()
    click.echo(f"Unlinked {bead_id} (was #{existing.gh_issue_num} in {existing.gh_repo})")


@gh_group.command("triage")
def gh_triage() -> None:
    """Review unlinked GitHub issues and import/link/ignore them.

    Lists GitHub issues that are not linked to any local bead,
    and lets you import them (create local bead), link to an
    existing bead, or skip.
    """
    config = _require_gh_config()
    repo = config.github.repo
    if not repo:
        click.echo("Error: No repo configured. Run 'purser gh attach' first.", err=True)
        raise SystemExit(1)

    from purser.gh.guard import require_gh_cli
    from purser.gh.issues import list_issues

    require_gh_cli(lambda: None)()  # Check gh availability

    store = _get_sync_store()

    # Get all linked GH issue numbers
    all_states = store.list_all()
    linked_nums = {s.gh_issue_num for s in all_states if s.gh_issue_num}

    # Fetch open GH issues
    gh_issues = list_issues(repo, state="open")
    unlinked = [i for i in gh_issues if i.get("number") not in linked_nums]

    if not unlinked:
        click.echo("All GitHub issues are linked to local beads.")
        store.close()
        return

    click.echo(f"Found {len(unlinked)} unlinked GitHub issues:\n")

    for gh_issue in unlinked:
        num = gh_issue.get("number")
        title = gh_issue.get("title", "")
        labels = [
            lbl["name"] if isinstance(lbl, dict) else lbl for lbl in gh_issue.get("labels", [])
        ]
        label_str = f" [{', '.join(labels)}]" if labels else ""

        click.echo(f"  #{num}: {title}{label_str}")
        action = click.prompt(
            "    Action",
            type=click.Choice(["import", "link", "skip"]),
            default="skip",
        )

        if action == "import":
            from purser.beads import create_issue as create_bead

            bead = create_bead(title, description=gh_issue.get("body", ""))
            from purser.gh.sync_store import SyncState

            store.upsert(
                SyncState(
                    bead_id=bead.id,
                    gh_repo=repo,
                    gh_issue_num=num,
                    sync_status="synced",
                )
            )
            click.echo(f"    Imported as {bead.id}")
        elif action == "link":
            bead_id = click.prompt("    Bead ID to link")
            from purser.gh.sync_store import SyncState

            store.upsert(
                SyncState(
                    bead_id=bead_id,
                    gh_repo=repo,
                    gh_issue_num=num,
                    sync_status="unlinked",
                )
            )
            click.echo(f"    Linked {bead_id} → #{num}")

    store.close()
    click.echo("\nTriage complete.")


@gh_group.command("sync")
@click.option("--dry-run", is_flag=True, help="Preview without applying changes")
def gh_sync(dry_run: bool) -> None:
    """Full bidirectional sync between local beads and GitHub.

    Pushes local changes, pulls remote changes, and handles conflicts
    according to the configured conflict_strategy.
    """
    config = _require_gh_config()

    from purser.gh.sync_engine import full_sync

    store = _get_sync_store()

    click.echo("Starting bidirectional sync...")
    stats = full_sync(config.github, store, dry_run=dry_run)

    store.close()
    click.echo("\nSync complete:")
    click.echo(f"  Created: {stats['created']}")
    click.echo(f"  Pushed:  {stats['pushed']}")
    click.echo(f"  Pulled:  {stats['pulled']}")
    click.echo(f"  Conflicts: {stats['conflicts']}")


@gh_group.command("push")
@click.option("--dry-run", is_flag=True, help="Preview without applying changes")
def gh_push(dry_run: bool) -> None:
    """Push local bead changes to GitHub.

    Creates new GH issues for unlinked beads and updates
    existing ones where local changes are detected.
    """
    config = _require_gh_config()
    repo = config.github.repo
    if not repo:
        click.echo("Error: No repo configured.", err=True)
        raise SystemExit(1)

    from purser.beads import list_issues as bd_list
    from purser.gh.sync_engine import push_dirty_issues, push_new_issues

    store = _get_sync_store()
    issues = bd_list()

    click.echo("Pushing to GitHub...")
    created = push_new_issues(issues, config.github, store, dry_run=dry_run)
    updated = push_dirty_issues(issues, config.github, store, dry_run=dry_run)

    store.close()
    click.echo(f"\nPush complete: {created} created, {updated} updated")


@gh_group.command("pull")
@click.option("--dry-run", is_flag=True, help="Preview without applying changes")
def gh_pull(dry_run: bool) -> None:
    """Pull GitHub changes to local beads.

    Fetches remote GH issue changes and updates local bead state.
    """
    config = _require_gh_config()

    from purser.gh.sync_engine import pull_remote_changes

    store = _get_sync_store()

    click.echo("Pulling from GitHub...")
    updated = pull_remote_changes(config.github, store, dry_run=dry_run)

    store.close()
    click.echo(f"\nPull complete: {updated} updated")
