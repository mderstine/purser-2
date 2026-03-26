---
name: purser-build-one
description: Claim the next ready bead (issue) from the purser queue without building it. Finds the next available (unblocked) issue and claims it for the user to work on manually.
allowed-tools: Bash
---

# Purser Build One

## Instructions

1. Run `bd ready --limit 1` to find the next available (unblocked) bead.
2. If no ready issues exist, report "No ready issues found. Run `bd ready` to see all available work."
3. Claim the issue: `bd update <id> --claim`
4. Read and display the issue details: `bd show <id>`
5. Report the claimed issue ID and remind the user they can now work on it manually.

## Workflow

```
1. DISCOVER: bd ready --limit 1
2. CLAIM: bd update <id> --claim
3. DISPLAY: bd show <id>
```

## Example prompts

- "/purser-build-one"
- "/purser-build-one Claim the next task for me"

## Output

Reports the claimed issue ID, title, and status. The user can then work on it manually and close it with `bd close <id>` when done.
