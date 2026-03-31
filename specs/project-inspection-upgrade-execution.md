---
id: spec-project-inspection-upgrade-execution
title: Project Inspection and Upgrade Execution
created: 2026-03-31
source: inline
---

# Project Inspection and Upgrade Execution

## Problem Statement

Purser can intake specs, decompose them into Beads work, and scaffold agent workflows for VS Code, Claude, and Codex, but the current project lacks a single spec focused on inspecting the repository's actual state before proposing upgrades. That gap makes it harder to drive upgrades from real implementation constraints, especially in the VS Code workflow where prompts, hooks, and generated scaffolding need to line up with the `spec -> planner -> executor` loop. The GitHub integration also needs explicit attention because syncing Beads issues to GitHub Issues is only part of the desired outcome; teams also need those synced issues reflected in GitHub Projects.

## Goals

- Add a first-class spec that starts with inspection of the current repository state before planning upgrade work.
- Treat the VS Code path as a primary execution surface, not an afterthought, and verify the generated prompts/hooks support the intended Purser loop.
- Validate the `spec -> planner -> executor` workflow with sandbox-friendly tests where practical.
- Ensure GitHub integration covers both GitHub Issues and GitHub Project items so Beads work can appear in project boards.
- Capture implementation gaps and follow-up work as explicit plan items rather than implicit assumptions.

## Non-Goals

- Replacing the existing GitHub integration spec for the full bidirectional architecture.
- Building a new VS Code extension or a custom execution runtime outside the existing generated prompts/hooks model.
- Adding real-time webhook sync or any non-CLI GitHub transport.
- Solving every future upgrade category in one pass; this spec should drive bounded, inspectable improvements.

## User Stories

- As a maintainer, I can ask Purser to inspect the current project and produce upgrade work based on the repository's actual state.
- As a VS Code user, I can scaffold the workspace, add a spec, create a plan, and run the build loop with prompts and hooks that reflect the same workflow contract.
- As a PM agent, I can turn an upgrade spec into Beads issues that match the implementation surfaces Purser actually exposes today.
- As a developer using GitHub Projects, I can sync Beads-backed work into both GitHub Issues and the configured GitHub Project board.

## Technical Constraints

- The inspection step must rely on local repository state and existing Purser configuration files.
- Sandbox validation should prefer deterministic tests and mocked GitHub/Beads boundaries over live network access.
- VS Code validation should focus on generated scaffolding, prompt instructions, and hook behavior because those are the current implementation surface.
- GitHub integration must remain optional and continue to work through the `gh` CLI.

## Acceptance Criteria

- [ ] A structured spec exists that explicitly frames project inspection as the first step in upgrade planning.
- [ ] The spec calls out the current VS Code implementation surface: generated agents, prompts, hooks, and workspace docs.
- [ ] Tests cover the intended `spec -> planner -> executor` flow at the prompt/scaffolding level, including VS Code command coverage.
- [ ] GitHub sync behavior includes configured GitHub Project item synchronization, not only GitHub Issue creation/update.
- [ ] The implementation remains idempotent when re-syncing previously linked GitHub Project items.
- [ ] The resulting plan can be decomposed into Beads work items without inventing implementation surfaces that do not exist in the repository.

## Open Questions

- Should project inspection become a distinct CLI command in the future, or remain a spec/planning convention?
- How much of the VS Code loop should be validated with end-to-end integration tests versus generated file assertions?
- Should GitHub Project field sync eventually map dependency relationships using GH issue numbers rather than local bead IDs?
