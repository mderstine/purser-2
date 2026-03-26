---
name: purser-build
description: Claim and build the next available bead (issue) from the purser queue. Finds the next ready (unblocked) issue, claims it, and works on it until completion.
allowed-tools: [Bash, Read, Edit, Write, Agent]
---

# Purser Build

## Instructions

1. Run `bd ready --limit 1` or `purser work next --limit 1` to find the next available (unblocked) bead.
2. If no ready issues exist, report "No ready issues found. Run `bd ready` to see all available work."
3. Claim the issue: `bd update <id> --claim`
4. Read the issue details: `bd show <id>`
5. Check for any associated spec file if mentioned in the issue.
6. Implement the feature/fix according to the issue description and acceptance criteria.
7. Run `purser lint` to validate code quality.
8. When complete, close the issue: `bd close <id> --reason "<summary of what was done>"`
9. Report completion with the issue ID and summary.

## Workflow

```
1. DISCOVER: bd ready --limit 1
2. CLAIM: bd update <id> --claim
3. UNDERSTAND: bd show <id>
4. IMPLEMENT: Edit code, write tests, etc.
5. VALIDATE: purser lint
6. COMPLETE: bd close <id> --reason "..."
```

## Rules

- Work on exactly ONE bead per invocation
- Always claim before starting work
- Always run lint before closing
- If you discover unrelated issues during work, file them with `bd create` or `purser work discover`
