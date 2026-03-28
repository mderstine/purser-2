#!/usr/bin/env python3
"""VS Code PostToolUse hook that reminds the model to run Purser quality gates."""

from __future__ import annotations

import json
import sys


def main() -> int:
    payload = json.load(sys.stdin)
    tool_name = payload.get("tool_name")

    if tool_name != "editFiles":
        return 0

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": (
                        "You edited files. Before closing the current bead, run the "
                        "relevant quality gates such as `purser lint`, targeted tests, "
                        "and any build commands needed for the touched code."
                    ),
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
