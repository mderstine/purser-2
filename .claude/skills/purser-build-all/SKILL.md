---
name: purser-build-all
description: Iteratively build all available beads in the purser queue until empty. Processes beads sequentially or forks independent beads to subagents for parallel execution.
allowed-tools: [Bash, Read, Edit, Write, Agent]
---

# Purser Build All

## Instructions

1. Run `bd ready` to get all available (unblocked) beads.
2. If no ready issues exist, report "Queue is empty - no ready issues found."
3. Analyze dependencies between ready issues using `bd dep tree <id>` where needed.
4. For each ready issue:
   - If the issue has no dependencies on other ready issues → fork to a subagent via `Agent` tool
   - If the issue depends on other ready issues → process sequentially after dependencies complete
5. Each subagent/worker should:
   - Claim the issue: `bd update <id> --claim`
   - Read the issue: `bd show <id>`
   - Implement the feature/fix
   - Run `purser lint` to validate
   - Close the issue: `bd close <id> --reason "<summary>"`
6. Continue until `bd ready` returns empty.
7. Report summary of completed issues.

## Subagent Pattern for Parallel Beads

When forking independent beads to subagents:

```python
Agent(
    subagent_type="general-purpose",
    description=f"Build bead {issue_id}",
    prompt=f"""
    You are a worker agent. Complete this bead:

    1. Claim: bd update {issue_id} --claim
    2. Read: bd show {issue_id}
    3. Implement the feature/fix according to the issue
    4. Validate: purser lint
    5. Close: bd close {issue_id} --reason "<what was done>"

    Work in: /home/md/src/repos/purser-2
    """
)
```

## Dependency Analysis

- Run `bd dep tree <id>` to see what an issue depends on
- If A depends on B, and both are ready → process B first, then A
- If A and B are independent → fork both in parallel

## Workflow

```
1. DISCOVER: bd ready
2. ANALYZE: Check dependencies for each ready issue
3. FORK: Spawn subagents for independent beads
4. SEQUENTIAL: Work on dependent beads in order
5. VALIDATE: Ensure all beads are closed
6. REPORT: Summary of completed work
```

## Rules

- Always claim before working
- Never work on unclaimed beads
- Respect dependencies - don't start dependent work until prerequisites complete
- Run lint before closing any bead
- Stop when `bd ready` returns empty
