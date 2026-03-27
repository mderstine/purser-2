---
id: spec-github-integration-sync
title: "GitHub Integration: Bidirectional Sync with GH Repos and Projects"
created: 2026-03-26
source: inline
---

# GitHub Integration: Bidirectional Sync with GH Repos and Projects

## Problem Statement

Purser currently operates as a local-only project management framework backed by Beads (Dolt) and DuckDB. Teams using GitHub for code hosting and project tracking have no way to mirror their purser work items to GitHub Issues or GitHub Projects, forcing manual duplication of effort. We need an optional GitHub integration layer that keeps the local beads database as the source of truth while synchronizing state bidirectionally with GitHub repos and GitHub Projects via the `gh` CLI.

## Goals

- **Offline-first**: Purser must work fully without GitHub. GH integration is opt-in via configuration.
- **Bidirectional sync**: Local beads changes push to GitHub; remote GitHub changes pull to beads.
- **Hierarchy mapping**: Map purser's work hierarchy to GitHub's native constructs (Issues, Projects, milestones, labels).
- **Dependency tracking**: Parent/child and blocks/blocked-by relationships are represented in both systems.
- **Metadata parity**: All relevant metadata (owner, dates, priority, effort, status) syncs between systems.
- **Conflict resolution**: Handle divergent edits gracefully with a clear strategy.

## Non-Goals

- Replacing GitHub Projects' native UI or workflow automation (Actions, automations).
- Supporting non-GitHub forges (GitLab, Gitea) in this spec (but architecture should not preclude them).
- Real-time webhooks or event-driven sync — this is CLI-triggered.
- Modifying the `gh` CLI itself.

---

## Proposed Hierarchy

### Recommended 5-Level Structure

Project management hierarchies balance granularity with usability. Here is the recommended mapping:

| Level | Purser Concept | GitHub Mapping | Purpose |
|-------|---------------|----------------|---------|
| **1. Objective** | Top-level goal | **GitHub Project (Board)** | Strategic outcome ("Launch v2.0", "SOC2 Compliance"). One purser project may map to one GH Project. |
| **2. Epic** | Large initiative | **GitHub Milestone** + **Label** `epic:<slug>` | A body of work delivering a coherent capability. Milestones give progress tracking; labels give filterability. |
| **3. Feature** | Functional component | **GitHub Issue** (label `type:feature`) | A user-facing capability within an epic. Represented as a GH Issue with sub-tasks. |
| **4. Task** | Implementation unit | **GitHub Issue** (label `type:task`) | A developer-assignable unit of work. Most day-to-day work lives here. |
| **5. Sub-task** | Atomic step | **GitHub Task List** (within parent issue body) | Checklist items within a task issue. Lightweight, no separate issue needed unless promoted. |

### Why This Mapping Works

- **Objectives as Projects**: GitHub Projects (v2) are boards with custom fields, views, and automations — ideal for tracking strategic goals across multiple repos.
- **Epics as Milestones**: Milestones have due dates, progress bars, and group issues naturally. The `epic:<slug>` label adds cross-repo filtering.
- **Features & Tasks as Issues**: GitHub Issues are the universal work unit. Distinguishing them via labels (`type:feature` vs `type:task`) preserves hierarchy while keeping GitHub's flat issue list usable.
- **Sub-tasks as Task Lists**: GitHub's task list syntax (`- [ ] description`) within issue bodies avoids issue sprawl for trivial items.

### Hierarchy Alternatives Considered

- **Objectives as Repos**: Too coarse; most teams have one repo per service, not per objective.
- **Epics as Issues**: Loses milestone progress tracking. Could work for smaller projects — configurable.
- **Sub-objectives**: Omitted from the default hierarchy. For large orgs, sub-objectives can be represented as nested GitHub Projects or as epics with a `sub-objective:<parent>` label. The system should support arbitrary nesting depth via parent/child links, but the default is the 5 levels above.

---

## Dependency & Relationship Tracking

### Dependency Types

| Relationship | Purser (Beads) | GitHub Representation |
|-------------|---------------|----------------------|
| **blocks** | `dependency.type = "blocks"` | Issue body footer: `Blocks: #123, #456` + Project field |
| **blocked-by** | Inverse of blocks | Issue body footer: `Blocked by: #789` + Project field |
| **parent-child** | `issue.parent = "<parent_id>"` | Issue body header: `Parent: #42` + sub-issue linking (if available) |
| **relates-to** | `dependency.type = "relates-to"` | Issue body: `Related: #101` |
| **discovered-from** | `dependency.type = "discovered-from"` | Issue body: `Discovered from: #55` |

### Orchestration

- The `purser work next` command already resolves unblocked issues. With GH sync, it should also check that upstream dependencies (GH issues in other repos) are closed.
- A new `purser sync` command will reconcile local and remote state, updating dependency links in both directions.
- GitHub Projects custom fields (`Blocked`, `Blocking`) enable Kanban views filtered by dependency status.

---

## Metadata Schema

### Core Fields (synced bidirectionally)

| Field | Purser Model | GitHub Mapping | Notes |
|-------|-------------|----------------|-------|
| `id` | `issue.id` | GitHub Issue number (`#123`) | Mapping stored in `.purser/gh_sync.json` |
| `title` | `issue.title` | Issue title | |
| `description` | `issue.description` | Issue body | Markdown, with dependency footer section |
| `type` | `issue.type` | Label: `type:{task,feature,epic,bug,chore}` | |
| `status` | `issue.status` | Issue state (`open`/`closed`) + Project column | `in_progress` maps to a Project status field |
| `priority` | `issue.priority` (0-4) | Label: `priority:{critical,high,medium,low,backlog}` + Project field | 0=critical, 4=backlog |
| `assignee` | `issue.assignee` | Issue assignee (GH username) | Configurable local↔GH username map |
| `labels` | `issue.labels` | Issue labels | Bidirectional sync, with configurable prefix filter |
| `parent` | `issue.parent` | Issue body: `Parent: #N` + sub-issue link | |
| `dependencies` | `issue.dependencies[]` | Issue body footer section | Parsed/generated on sync |
| `created_at` | `issue.created_at` | Issue `created_at` | Read-only from GH |
| `updated_at` | `issue.updated_at` | Issue `updated_at` | Used for conflict detection |

### Extended Fields (new, stored in `issue.metadata`)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `owner` | `str` | None | Who is accountable (may differ from assignee) |
| `start_date` | `date` | None | When work actually began |
| `end_date` | `date` | None | When work was completed |
| `due_date` | `date` | None | Target completion date |
| `estimated_effort` | `str` | None | T-shirt size or hours (e.g., "S", "M", "L", "2h") |
| `actual_effort` | `str` | None | Recorded after completion |
| `milestone` | `str` | None | Epic/milestone name |
| `gh_issue_number` | `int` | None | GitHub issue number for cross-reference |
| `gh_project_item_id` | `str` | None | GitHub Project item ID for field updates |
| `gh_repo` | `str` | None | `owner/repo` for multi-repo support |
| `last_synced_at` | `datetime` | None | Last successful sync timestamp |
| `sync_hash` | `str` | None | Content hash at last sync for conflict detection |

---

## Configuration

### `purser.toml` additions

```toml
[github]
enabled = false                  # Master switch
repo = "owner/repo"              # Default GH repo
project = "My Project"           # GH Project name or number
sync_on_commit = false           # Auto-sync on `purser work done`
conflict_strategy = "local-wins" # local-wins | remote-wins | prompt
label_prefix = ""                # Optional prefix for purser-managed labels
username_map = { "local_user" = "gh_username" }

# Multi-repo support (optional)
[[github.repos]]
name = "owner/frontend"
labels = ["frontend"]

[[github.repos]]
name = "owner/backend"
labels = ["backend"]
```

### Environment Variables

- `PURSER_GH_ENABLED=1` — enable without editing config
- `PURSER_GH_REPO=owner/repo` — override default repo
- `PURSER_GH_PROJECT=3` — project number

---

## CLI Commands

### New Commands

| Command | Description |
|---------|-------------|
| `purser gh attach` | Configure GitHub repo and project for current purser instance |
| `purser gh sync` | Full bidirectional sync (push local changes, pull remote changes) |
| `purser gh push` | Push local state to GitHub (create/update issues, project items) |
| `purser gh pull` | Pull remote state from GitHub (update local beads) |
| `purser gh status` | Show sync status: pending changes, conflicts, last sync time |
| `purser gh link <bead_id> <gh_issue>` | Manually link a local bead to an existing GH issue |
| `purser gh unlink <bead_id>` | Remove GH association from a bead |
| `purser gh triage` | Interactive: review unlinked GH issues and import/link/ignore |

### Enhanced Existing Commands

- `purser work done` — optionally triggers `gh sync` if `sync_on_commit = true`
- `purser plan create` — optionally creates GH issues and project items for the generated plan
- `purser init` — prompts for GitHub configuration if `gh` CLI is detected

---

## Sync Architecture

### Sync Engine Design

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│  Beads DB   │◄────►│  Sync Engine │◄────►│  GH CLI     │
│  (local)    │      │  (purser)    │      │  (gh api)   │
└─────────────┘      └──────────────┘      └─────────────┘
                            │
                     ┌──────┴──────┐
                     │ Sync State  │
                     │ (.purser/   │
                     │  gh_sync.db)│
                     └─────────────┘
```

### Sync State Store

A DuckDB table (in `.purser/gh_sync.db` or the existing `memory.duckdb`) tracking:

```sql
CREATE TABLE gh_sync_map (
    bead_id       TEXT PRIMARY KEY,
    gh_repo       TEXT NOT NULL,
    gh_issue_num  INTEGER,
    gh_project_id TEXT,
    content_hash  TEXT,       -- hash of synced content for conflict detection
    last_synced   TIMESTAMP,
    sync_status   TEXT        -- 'synced', 'local-dirty', 'remote-dirty', 'conflict'
);
```

### Conflict Resolution

1. Compute content hash of both local and remote state.
2. Compare against `content_hash` at last sync.
3. If only one side changed → apply that side's changes.
4. If both changed → apply `conflict_strategy` from config:
   - `local-wins`: Local overwrites remote.
   - `remote-wins`: Remote overwrites local.
   - `prompt`: Show diff and ask user.

---

## User Stories

- As a solo developer, I can run `purser gh attach` to connect my local purser to my GitHub repo and project, then `purser gh sync` to push all my beads as GitHub Issues.
- As a team lead, I can view purser-generated plans in GitHub Projects with proper status columns, priorities, and dependency fields.
- As a contributor, I can close a GitHub Issue and have `purser gh pull` update the local bead status.
- As an offline developer, I can work locally with purser and sync when I'm back online.
- As a multi-repo maintainer, I can configure multiple repos and have issues routed to the correct repo based on labels.

## Technical Constraints

- Python 3.10+
- `gh` CLI must be installed and authenticated (detected at runtime, not a hard dependency)
- All GH API calls go through `gh api` (not direct HTTP) for auth consistency
- Sync operations must be idempotent and safe to re-run
- No new Python dependencies for the GH integration (use `gh` CLI subprocess calls)

## Acceptance Criteria

- [ ] `purser gh attach` configures repo and project in `purser.toml`
- [ ] `purser gh sync` creates GH Issues for all local beads with correct labels and metadata
- [ ] `purser gh sync` updates local beads from GH Issue changes (status, assignee, labels)
- [ ] Parent/child relationships rendered in GH Issue bodies and parsed back on pull
- [ ] Dependency links (blocks/blocked-by) rendered and parsed in GH Issue bodies
- [ ] GitHub Project items created with custom fields (Status, Priority, Type)
- [ ] Conflict detection works: divergent edits are flagged, not silently overwritten
- [ ] All commands work without `gh` CLI installed (graceful degradation with clear message)
- [ ] `purser gh status` shows pending changes and last sync time
- [ ] Extended metadata fields (owner, dates, effort) stored in `issue.metadata` and synced to GH Project fields
- [ ] Multi-repo configuration works for cross-repo issue routing
- [ ] Integration tests using `gh` CLI mock or test repo

## Open Questions

- Should we support GitHub Actions for automated sync (e.g., on issue close, trigger purser update)?
- How granular should task list sync be — should promoting a sub-task to a full issue be automated?
- Should we support GitHub Discussions for specs/RFCs in addition to Issues?
- What's the right behavior when a GH Issue is deleted remotely — soft-delete locally or flag for review?
- Should sync support GitHub Issue templates to standardize the format of created issues?
