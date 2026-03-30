---
id: spec-repo-initialization-routine
title: "Repository Initialization Routine for Purser, Beads/Dolt, and Optional GitHub Coordination"
created: 2026-03-30
source: inline
---

# Repository Initialization Routine for Purser, Beads/Dolt, and Optional GitHub Coordination

## Problem Statement

Purser has the beginning of an initialization flow in `purser init`, but the experience is still incomplete and under-documented for a fresh repository. A user who wants to adopt Purser in a new or existing repo needs a clear, repeatable way to:

- initialize local Purser state
- create the Beads/Dolt database and verify it is usable
- understand what was created and where it lives
- optionally connect the repo to GitHub Issues and GitHub Projects
- understand the next commands to run after initialization

Today, those steps are spread across CLI behavior, README prose, and separate GitHub integration docs. The result is ambiguity at the exact point where the user is trying to bootstrap the workflow.

## Goals

- Provide a single, explicit initialization routine for a Purser-enabled repository.
- Ensure local-first setup works without GitHub or network access.
- Make Beads/Dolt setup a first-class part of initialization, not an implied side effect.
- Offer an optional GitHub coordination path for repository and project setup.
- Produce onboarding documentation that is strong enough for both human users and agent hosts.
- Make it obvious how to verify initialization and how to recover from partial setup.

## Non-Goals

- Replacing `bd` or Dolt with a Purser-native issue tracker.
- Making GitHub integration mandatory for local Purser usage.
- Solving every multi-repo workflow in this spec.
- Automating GitHub authentication beyond guiding the user into `gh auth login`.
- Designing a full installer for external host tools beyond the initialization entrypoint.

## Current State

The current `purser init` command:

- creates `specs/`, `formulas/`, and `.purser/`
- initializes `.purser/memory.duckdb`
- attempts `bd init`
- prints a generic success message and a minimal next-step suggestion

The current gaps are:

- no explicit explanation of what `bd init` created or whether the Beads/Dolt database is healthy
- no structured status report for partial initialization
- no guided optional GitHub setup path as part of repo bootstrap
- no consolidated initialization document that a new user can follow end-to-end
- limited distinction between local-only initialization and GitHub-connected initialization

## User Stories

- As a solo developer, I can run one initialization routine and get a working local Purser repo without touching GitHub.
- As a developer using Beads for the first time, I can tell whether the local Beads/Dolt state was created correctly and what command to run if it was not.
- As a developer working in a GitHub-backed repo, I can optionally attach the current repository and a GitHub Project during initialization.
- As an AI agent host, I can rely on a documented initialization contract to bootstrap a repo consistently before doing planning or execution work.
- As a maintainer, I can point contributors to one setup guide instead of explaining local setup and GitHub setup separately.

## Proposed Experience

### Primary Command

The primary entrypoint remains:

```bash
purser init
```

This command should become the canonical repo bootstrap routine.

### Initialization Modes

Initialization should be clearly understood as two layers:

1. Local foundation, always available
2. Optional GitHub coordination, only when requested and supported

#### 1. Local Foundation

Local initialization should:

- create required directories such as `specs/`, `formulas/`, and `.purser/`
- initialize DuckDB memory storage at `.purser/memory.duckdb`
- initialize Beads in the repo via `bd init`
- verify that `bd` is available before attempting Beads setup
- report the resulting local filesystem and database state in a way that is easy to scan

The command should treat local initialization as successful only when the repo has:

- Purser config resolved successfully
- required directories present
- DuckDB memory database created or confirmed
- Beads initialized or explicitly reported as unavailable

#### 2. Optional GitHub Coordination

After local initialization succeeds, the user should be able to opt into GitHub coordination.

This can happen either:

- inline during `purser init` when `gh` is installed and authenticated
- or as an explicit follow-up command: `purser gh attach`

GitHub coordination should support:

- detecting the current GitHub repository when possible
- prompting for or accepting `owner/repo`
- optionally prompting for a GitHub Project name or number
- writing the `[github]` section to `purser.toml`
- clearly distinguishing “GitHub configured” from “GitHub synced”

The routine should not imply that `gh attach` also performs synchronization. It should tell the user the next step is `purser gh sync`.

## Detailed Workflow

### Happy Path: Local-Only Repo

```bash
purser init
```

Expected flow:

1. Detect existing initialization state.
2. Create missing local directories.
3. Initialize or validate `.purser/memory.duckdb`.
4. Run `bd init`.
5. Print a compact summary of created and verified resources.
6. Print next steps for spec creation, planning, and work execution.

Expected summary should include:

- config file source, if any
- memory database path
- specs directory path
- formulas directory path
- Beads status
- whether GitHub integration is configured or not

### Happy Path: Repo with GitHub Coordination

```bash
purser init
purser gh attach
purser gh sync
```

Or, if initialization becomes interactive:

```bash
purser init --with-github
```

Expected flow:

1. Complete local initialization.
2. Verify `gh` is installed and authenticated.
3. Detect or prompt for the GitHub repo.
4. Prompt for optional GitHub Project name or number.
5. Write `[github]` config into `purser.toml`.
6. Explain that `purser gh sync` is the first synchronization step.

### Partial Failure and Recovery

Initialization must produce actionable recovery guidance in at least these cases:

- `bd` CLI missing
- `gh` CLI missing
- `gh` installed but not authenticated
- memory DB path not writable
- repo already initialized
- GitHub configuration already present

Recovery guidance should prefer exact commands, for example:

- `brew install beads`
- `gh auth login`
- `purser init --check`
- `purser gh status`
- `purser gh attach --repo owner/repo`

## Proposed CLI and UX Changes

### `purser init`

`purser init` should evolve from a minimal bootstrap helper into a documented setup routine.

Recommended capabilities:

- `purser init`
  local setup only, with status summary
- `purser init --check`
  report current initialization health without changing anything
- `purser init --force`
  allow re-running initialization intentionally
- `purser init --with-github`
  after local setup, enter the GitHub attachment path
- `purser init --repo owner/repo`
  optional non-interactive GitHub repo input when combined with `--with-github`
- `purser init --project <name-or-number>`
  optional non-interactive GitHub Project input

If interactive prompting is undesirable in `purser init`, the alternative is:

- keep `purser init` local-only
- improve its summary output
- document `purser gh attach` as the supported second step

Either approach is acceptable as long as the documentation is explicit and the user journey is coherent.

### `purser gh attach`

This command remains the canonical GitHub configuration step. It should be documented as:

- optional
- safe to run after `purser init`
- configuration-only, not a sync operation

### `purser init --check`

The status output should report at least:

- whether `specs/` exists
- whether `formulas/` exists
- whether `.purser/` exists
- whether `.purser/memory.duckdb` exists
- whether `bd` is installed
- whether Beads appears initialized for this repo
- whether `gh` is installed
- whether GitHub integration is configured in `purser.toml`
- whether any GitHub sync state exists

## Files and State Created

The initialization documentation should explicitly describe these resources:

### Local State

- `purser.toml`
  repo configuration, including optional `[github]`
- `.purser/memory.duckdb`
  DuckDB memory store
- Beads repository state created by `bd init`
  local issue tracking state backed by Dolt/Beads
- `specs/`
  structured spec documents
- `formulas/`
  reusable planning templates

### Optional GitHub-Related State

- `[github]` section in `purser.toml`
- `.purser/gh_sync.duckdb`
  sync state created once GitHub synchronization begins

The docs should explicitly call out that GitHub sync state may not exist immediately after `purser gh attach`; it is created once sync activity starts.

## Documentation Deliverables

This work should produce or update documentation in at least these places:

- README setup section
- a dedicated initialization guide or setup guide
- command help text for `purser init`
- command help text for `purser gh attach`

The documentation should answer:

- what `purser init` does
- what it does not do
- what files it creates
- how Beads/Dolt fits in
- how GitHub setup is optional
- what command to run next for local-only usage
- what command to run next for GitHub-connected usage

## Acceptance Criteria

- A new user can initialize a repo locally without reading source code.
- A new user can tell whether Beads/Dolt setup succeeded.
- A new user can understand that GitHub setup is optional and separate from local initialization.
- The docs show the exact commands for both local-only and GitHub-connected setups.
- The docs explain the created local files and state, including memory DB and GitHub sync DB.
- `purser init --check` reports enough detail to debug partial setup.
- The initialization flow does not require network access unless the user opts into GitHub coordination.
- The initialization flow does not silently conflate configuration with synchronization.

## Example Documentation Snippet

```bash
# Local-only setup
uv run purser init

# Verify setup
uv run purser init --check

# Optional GitHub coordination
uv run purser gh attach --repo owner/repo --project "Roadmap"
uv run purser gh sync
```

## Open Questions

- Should `purser init` remain strictly non-interactive by default, or should it offer an opt-in interactive GitHub branch?
- Should Beads health verification go beyond “`bd` exists and `bd init` returned success” and inspect repo-local Beads metadata directly?
- Should `purser init` create a starter `purser.toml` when none exists, or continue relying on implicit defaults plus optional later edits?
- Should `purser init` offer to scaffold host-specific agent files such as `purser launch vscode`, `purser launch claude`, and `purser launch codex`, or should that remain a separate concern?
