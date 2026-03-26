---
name: purser-plan
description: Decompose specs into atomic tasks with dependencies. If spec_id provided, decomposes just that spec. Otherwise, reads all specs and creates a complete plan with dependencies.
allowed-tools: [Bash, Read, Agent]
---

# Purser Plan

## Instructions

Decompose specification(s) into atomic tasks (beads) with proper dependencies.

### Mode 1: Specific Spec
If user provides a spec_id:
1. Run `purser spec show <spec_id>` to read the spec
2. Analyze the spec's sections (Goals, User Stories, Acceptance Criteria, etc.)
3. Create atomic beads using `bd create` for each task
4. Add dependencies between beads using `bd dep add`
5. Report the created plan with dependency tree

### Mode 2: All Specs
If no spec_id provided:
1. Run `purser spec list` to get all specs
2. For each spec that doesn't have a plan yet:
   - Read the spec content
   - Analyze and decompose into atomic tasks
   - Create beads with `bd create`
   - Add dependencies with `bd dep add`
3. Report summary of all created plans

## Decomposition Strategy

Break down each spec into 3 levels:
- **Epics** - Major deliverables (create as beads with type=epic)
- **Features** - Components of epics (create as beads with type=feature)
- **Tasks** - Atomic work units (create as beads with type=task)

## Dependency Patterns

- Sequential: Task B depends on Task A → `bd dep add task-b blocks task-a`
- Parallel: Tasks C and D can run together → no dependency between them
- Epic/Feature grouping: Features depend on Epics, Tasks depend on Features

## Commands

```bash
# List specs
purser spec list

# Show spec content
purser spec show <spec_id>

# Create beads at different levels
bd create "Epic: User Authentication" -t epic -p 1
bd create "Feature: OAuth Login" -t feature -p 2 --parent <epic_id>
bd create "Task: Implement OAuth flow" -t task -p 3 --parent <feature_id>

# Add dependencies
bd dep add <task-b> blocks <task-a>

# View dependency tree
bd dep tree <epic_id>
```

## Example prompts

- "/purser-plan spec-hello-world-multilingual" - Decompose specific spec
- "/purser-plan" - Decompose all specs
- "/purser-plan Create atomic tasks from specs"

## Output

Reports:
- Number of specs processed
- Number of epics, features, and tasks created
- Dependency trees for review
