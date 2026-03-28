#!/usr/bin/env python3
"""VS Code Stop hook that nudges the Purser build-all loop to continue."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_ready(repo_root: Path) -> list[dict]:
    result = subprocess.run(
        ["bd", "ready", "--json"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def main() -> int:
    payload = json.load(sys.stdin)
    repo_root = Path(payload.get("workspace_folder", "."))
    ready = _run_ready(repo_root)
    stop_hook_active = bool(payload.get("stop_hook_active"))

    if not ready:
        print(json.dumps({"systemMessage": "Purser hook: no ready beads remain."}))
        return 0

    if stop_hook_active:
        print(
            json.dumps(
                {
                    "systemMessage": (
                        "Purser hook: ready beads still remain, but the stop hook has "
                        "already re-entered the loop once. Stop if the remaining work "
                        "is intentionally blocked or unsafe."
                    )
                }
            )
        )
        return 0

    next_issue = ready[0]
    issue_id = next_issue.get("id", "unknown")
    title = next_issue.get("title", "next ready bead")
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "Stop",
                    "decision": "block",
                    "reason": (
                        f"Continue the Purser Ralph loop. Ready bead remains: {issue_id} "
                        f"({title}). Claim it and keep working unless a human decision "
                        "or safety concern prevents progress."
                    ),
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
