"""Core sync engine: push local→GH and pull GH→local.

Coordinates between the beads database, GitHub API, and sync state store.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import click

from purser.gh.content_hash import compute_content_hash
from purser.gh.issues import create_issue as gh_create_issue
from purser.gh.issues import get_issue as gh_get_issue
from purser.gh.issues import update_issue as gh_update_issue
from purser.gh.serializer import bead_to_gh_payload, gh_issue_to_bead_fields
from purser.gh.sync_store import SYNCED, SyncState

if TYPE_CHECKING:
    from purser.gh.sync_store import SyncStore
    from purser.models import GitHubConfig, Issue


def push_new_issues(
    issues: list[Issue],
    gh_config: GitHubConfig,
    sync_store: SyncStore,
    *,
    dry_run: bool = False,
) -> int:
    """Push unlinked local beads to GitHub as new issues.

    Returns count of issues pushed.
    """
    repo = gh_config.repo
    if not repo:
        return 0

    pushed = 0
    for issue in issues:
        # Skip if already linked
        existing = sync_store.get(issue.id)
        if existing and existing.gh_issue_num:
            continue

        payload = bead_to_gh_payload(issue, gh_config, sync_store)

        if dry_run:
            click.echo(f"  [dry-run] Would create GH issue: {issue.title}")
            pushed += 1
            continue

        gh_issue = gh_create_issue(
            repo,
            title=payload["title"],
            body=payload.get("body", ""),
            labels=payload.get("labels"),
            assignee=payload.get("assignee"),
        )

        content_hash = compute_content_hash(issue)
        now = datetime.now(UTC)

        sync_store.upsert(
            SyncState(
                bead_id=issue.id,
                gh_repo=repo,
                gh_issue_num=gh_issue["number"],
                content_hash=content_hash,
                last_synced=now,
                sync_status=SYNCED,
            )
        )

        click.echo(f"  Created #{gh_issue['number']}: {issue.title}")
        pushed += 1

    return pushed


def push_dirty_issues(
    issues: list[Issue],
    gh_config: GitHubConfig,
    sync_store: SyncStore,
    *,
    dry_run: bool = False,
) -> int:
    """Push locally-changed beads to update existing GH issues.

    Returns count of issues updated.
    """
    repo = gh_config.repo
    if not repo:
        return 0

    updated = 0
    for issue in issues:
        state = sync_store.get(issue.id)
        if not state or not state.gh_issue_num:
            continue

        current_hash = compute_content_hash(issue)
        if current_hash == state.content_hash:
            continue  # No actual change

        payload = bead_to_gh_payload(issue, gh_config, sync_store)

        if dry_run:
            click.echo(f"  [dry-run] Would update #{state.gh_issue_num}: {issue.title}")
            updated += 1
            continue

        gh_update_issue(
            repo,
            state.gh_issue_num,
            title=payload["title"],
            body=payload.get("body"),
            labels=payload.get("labels"),
            assignee=payload.get("assignee"),
            state="closed" if issue.status == "closed" else "open",
        )

        sync_store.mark_synced(issue.id, current_hash)
        click.echo(f"  Updated #{state.gh_issue_num}: {issue.title}")
        updated += 1

    return updated


def pull_remote_changes(
    gh_config: GitHubConfig,
    sync_store: SyncStore,
    *,
    dry_run: bool = False,
) -> int:
    """Pull changes from GitHub and update local beads.

    Returns count of issues updated locally.
    """
    repo = gh_config.repo
    if not repo:
        return 0

    all_states = sync_store.list_all()
    updated = 0

    for state in all_states:
        if not state.gh_issue_num:
            continue

        try:
            gh_issue = gh_get_issue(state.gh_repo or repo, state.gh_issue_num)
        except Exception:
            click.echo(f"  Warning: Could not fetch #{state.gh_issue_num}", err=True)
            continue

        fields = gh_issue_to_bead_fields(gh_issue, gh_config)

        if dry_run:
            click.echo(f"  [dry-run] Would pull #{state.gh_issue_num}: {fields['title']}")
            updated += 1
            continue

        # Update local bead via bd CLI
        from purser.beads import update_issue as bd_update

        update_kwargs = {}
        if fields.get("title"):
            update_kwargs["title"] = fields["title"]
        if fields.get("description"):
            update_kwargs["description"] = fields["description"]
        if fields.get("assignee"):
            update_kwargs["assignee"] = fields["assignee"]
        if fields.get("priority") is not None:
            update_kwargs["priority"] = fields["priority"]

        if update_kwargs:
            try:
                bd_update(state.bead_id, **update_kwargs)
            except Exception as e:
                click.echo(f"  Warning: Could not update {state.bead_id}: {e}", err=True)
                continue

        # Handle status changes
        if fields.get("status") == "closed":
            import contextlib

            from purser.beads import close_issue as bd_close

            with contextlib.suppress(Exception):
                bd_close(state.bead_id, reason="Closed via GitHub sync")

        # Compute new hash based on what we pulled and mark synced
        # We rebuild an Issue-like object for hashing
        from purser.models import Issue

        Issue.model_rebuild()
        synced_issue = Issue(
            id=state.bead_id,
            title=fields.get("title", ""),
            description=fields.get("description"),
            status=fields.get("status", "open"),
            priority=fields.get("priority", 2),
            type=fields.get("type", "task"),
            assignee=fields.get("assignee"),
            labels=fields.get("labels", []),
        )
        new_hash = compute_content_hash(synced_issue)
        sync_store.mark_synced(state.bead_id, new_hash)

        click.echo(f"  Pulled #{state.gh_issue_num}: {fields['title']}")
        updated += 1

    return updated


def push_to_project(
    issues: list[Issue],
    gh_config: GitHubConfig,
    sync_store: SyncStore,
    project_id: str,
    field_map: dict[str, str],
    *,
    dry_run: bool = False,
) -> int:
    """Add pushed issues to GH Project and set custom field values.

    Should be called after push_new_issues/push_dirty_issues.
    Returns count of project items updated.
    """
    from purser.gh.issues import get_issue as gh_get
    from purser.gh.project_fields import sync_item_fields
    from purser.gh.projects import add_item_to_project

    updated = 0
    repo = gh_config.repo
    if not repo:
        return 0

    for issue in issues:
        state = sync_store.get(issue.id)
        if not state or not state.gh_issue_num:
            continue

        if dry_run:
            click.echo(f"  [dry-run] Would add #{state.gh_issue_num} to project")
            updated += 1
            continue

        # Get the GH issue node ID for project operations
        gh_issue = gh_get(repo, state.gh_issue_num)
        node_id = gh_issue.get("node_id", "")
        if not node_id:
            continue

        # Add to project
        try:
            item_id = add_item_to_project(project_id, node_id)
        except Exception as e:
            click.echo(f"  Warning: Could not add #{state.gh_issue_num} to project: {e}", err=True)
            continue

        # Update custom fields
        sync_item_fields(
            project_id,
            item_id,
            field_map,
            issue.type,
            issue.priority,
        )

        # Store project item ID
        state.gh_project_id = item_id
        sync_store.upsert(state)

        click.echo(f"  Added #{state.gh_issue_num} to project")
        updated += 1

    return updated


def full_sync(
    gh_config: GitHubConfig,
    sync_store: SyncStore,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Perform a full bidirectional sync.

    1. Get all local beads
    2. Compute local dirty set
    3. Push new and dirty issues
    4. Pull remote changes (with conflict detection)
    5. Return summary stats

    Returns dict with keys: created, pushed, pulled, conflicts.
    """
    from purser.beads import list_issues as bd_list
    from purser.gh.conflict import ChangeClass, classify_change, resolve_conflict

    repo = gh_config.repo
    if not repo:
        return {"created": 0, "pushed": 0, "pulled": 0, "conflicts": 0}

    issues = bd_list()
    issue_map = {i.id: i for i in issues}
    stats = {"created": 0, "pushed": 0, "pulled": 0, "conflicts": 0}

    click.echo("Phase 1: Push local changes...")

    # Find unlinked beads and push them
    unlinked = [i for i in issues if not sync_store.get(i.id)]
    stats["created"] = push_new_issues(unlinked, gh_config, sync_store, dry_run=dry_run)

    # Find locally-dirty beads
    linked = [i for i in issues if sync_store.get(i.id)]
    stats["pushed"] = push_dirty_issues(linked, gh_config, sync_store, dry_run=dry_run)

    click.echo("\nPhase 2: Pull remote changes...")

    # For each linked bead, check for conflicts before pulling
    all_states = sync_store.list_all()
    for state in all_states:
        if not state.gh_issue_num:
            continue

        try:
            gh_issue = gh_get_issue(state.gh_repo or repo, state.gh_issue_num)
        except Exception:
            continue

        # Compute remote hash from GH issue
        fields = gh_issue_to_bead_fields(gh_issue, gh_config)
        from purser.models import Issue as IssueModel

        IssueModel.model_rebuild()
        remote_issue = IssueModel(
            id=state.bead_id,
            title=fields.get("title", ""),
            description=fields.get("description"),
            status=fields.get("status", "open"),
            priority=fields.get("priority", 2),
            type=fields.get("type", "task"),
            assignee=fields.get("assignee"),
            labels=fields.get("labels", []),
        )
        remote_hash = compute_content_hash(remote_issue)

        # Compute local hash
        local_issue = issue_map.get(state.bead_id)
        local_hash = compute_content_hash(local_issue) if local_issue else state.content_hash or ""

        change = classify_change(local_hash, remote_hash, state.content_hash)

        if change == ChangeClass.NO_CHANGE:
            continue
        elif change == ChangeClass.REMOTE_ONLY:
            # Safe to pull
            if not dry_run:
                from purser.beads import update_issue as bd_update

                update_kwargs = {}
                if fields.get("title"):
                    update_kwargs["title"] = fields["title"]
                if fields.get("assignee"):
                    update_kwargs["assignee"] = fields["assignee"]
                if update_kwargs:
                    try:
                        bd_update(state.bead_id, **update_kwargs)
                    except Exception:
                        continue
                sync_store.mark_synced(state.bead_id, remote_hash)
            click.echo(f"  Pulled #{state.gh_issue_num}: {fields.get('title', '')}")
            stats["pulled"] += 1
        elif change == ChangeClass.LOCAL_ONLY:
            # Already pushed above
            pass
        elif change == ChangeClass.CONFLICT:
            resolution = resolve_conflict(
                state.bead_id,
                gh_config.conflict_strategy,
                local_title=local_issue.title if local_issue else "",
                remote_title=fields.get("title", ""),
            )
            from purser.gh.conflict import Resolution

            if resolution == Resolution.USE_LOCAL:
                # Re-push local
                if local_issue and not dry_run:
                    push_dirty_issues([local_issue], gh_config, sync_store)
            elif resolution == Resolution.USE_REMOTE:
                # Apply remote
                if not dry_run:
                    import contextlib as _cl

                    from purser.beads import update_issue as bd_update

                    update_kwargs = {}
                    if fields.get("title"):
                        update_kwargs["title"] = fields["title"]
                    if update_kwargs:
                        with _cl.suppress(Exception):
                            bd_update(state.bead_id, **update_kwargs)
                    sync_store.mark_synced(state.bead_id, remote_hash)
            else:
                sync_store.mark_conflict(state.bead_id)
            stats["conflicts"] += 1

    return stats


def ensure_labels_on_repo(repo: str, prefix: str) -> None:
    """Ensure standard purser labels exist on the repo."""
    from purser.gh.hierarchy import ensure_type_labels

    ensure_type_labels(repo, prefix)
    click.echo(f"  Labels ensured on {repo}")
