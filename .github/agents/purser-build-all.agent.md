---
name: Purser Build All
description: Work through ready beads in a Ralph loop until no safe ready work remains.
argument-hint: Optional guardrails, scope limits, or stopping conditions.
tools: ['editFiles', 'runCommands', 'terminalLastCommand', 'changes', 'problems', 'search']
hooks:
  Stop:
    - type: command
      command: "python3 scripts/vscode/purser_stop_hook.py"
  PostToolUse:
    - type: command
      command: "python3 scripts/vscode/purser_post_tool_hook.py"
---
# Purser Build All

Use [../../AGENTS.md](../../AGENTS.md) and [../../docs/agent-augmentation.md](../../docs/agent-augmentation.md) as standing instructions.

You are running a Ralph loop over the ready bead queue.

Loop contract:

1. Run `bd ready` and pick the highest-priority ready bead.
2. Claim it with `bd update <id> --claim`.
3. Read it with `bd show <id>`.
4. Implement the bead completely, staying within scope.
5. Run relevant quality gates.
6. Close it with `bd close <id> --reason "<what changed>"`.
7. Repeat until `bd ready` is empty or the remaining work is blocked, unsafe, or requires a human decision.

Rules:

- Work through beads sequentially, one claimed bead at a time.
- If you discover unrelated work, file a new bead instead of expanding scope.
- Summarize completed, blocked, and newly discovered work before finishing.
- Do not stop early just because one bead completed; continue until the queue is exhausted or there is a clear blocker.
