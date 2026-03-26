"""Agent protocol: tool schemas and dispatch.

Defines the contract between purser and any LLM. Tool schemas use
OpenAI function-calling format (the de facto standard). The dispatch
function maps tool calls to purser functions.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from purser.memory import MemoryStore

# --- Tool definitions (OpenAI function-calling format) ---

TOOL_READY = {
    "name": "purser_ready",
    "description": "Get unblocked issues ready for work. Returns a list of issues that have no pending blockers.",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Max number of issues to return",
                "default": 10,
            },
        },
    },
}

TOOL_CLAIM = {
    "name": "purser_claim",
    "description": "Claim an issue for work. Sets status to in_progress.",
    "parameters": {
        "type": "object",
        "properties": {
            "issue_id": {"type": "string", "description": "The bd issue ID"},
        },
        "required": ["issue_id"],
    },
}

TOOL_SHOW = {
    "name": "purser_show",
    "description": "Show full details of an issue including description, dependencies, and notes.",
    "parameters": {
        "type": "object",
        "properties": {
            "issue_id": {"type": "string", "description": "The bd issue ID"},
        },
        "required": ["issue_id"],
    },
}

TOOL_CLOSE = {
    "name": "purser_close",
    "description": "Close an issue with a completion reason.",
    "parameters": {
        "type": "object",
        "properties": {
            "issue_id": {"type": "string", "description": "The bd issue ID"},
            "reason": {"type": "string", "description": "Why the issue is being closed"},
        },
        "required": ["issue_id"],
    },
}

TOOL_CREATE = {
    "name": "purser_create",
    "description": "Create a new issue (epic, feature, task, bug, or chore).",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Issue title"},
            "type": {
                "type": "string",
                "enum": ["epic", "feature", "task", "bug", "chore"],
                "default": "task",
            },
            "description": {"type": "string", "description": "Detailed description"},
            "priority": {
                "type": "integer",
                "description": "0=critical, 1=high, 2=medium, 3=low, 4=backlog",
                "default": 2,
            },
            "parent": {"type": "string", "description": "Parent issue ID"},
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Labels for categorization",
            },
        },
        "required": ["title"],
    },
}

TOOL_DISCOVER = {
    "name": "purser_discover",
    "description": "File a new issue for an unrelated problem discovered during work. Automatically links it to the source issue.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Issue title"},
            "description": {"type": "string", "description": "What was discovered"},
            "from_issue": {"type": "string", "description": "Issue ID where this was discovered"},
            "type": {
                "type": "string",
                "enum": ["bug", "task", "chore"],
                "default": "bug",
            },
        },
        "required": ["title", "from_issue"],
    },
}

TOOL_NOTE = {
    "name": "purser_note",
    "description": "Add a note to an issue for context or progress updates.",
    "parameters": {
        "type": "object",
        "properties": {
            "issue_id": {"type": "string", "description": "The bd issue ID"},
            "text": {"type": "string", "description": "Note content"},
        },
        "required": ["issue_id", "text"],
    },
}

TOOL_LIST = {
    "name": "purser_list",
    "description": "List issues with optional filters.",
    "parameters": {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["open", "in_progress", "closed"]},
            "type": {"type": "string", "enum": ["epic", "feature", "task", "bug", "chore"]},
            "label": {"type": "string", "description": "Filter by label"},
            "parent": {"type": "string", "description": "Filter by parent issue ID"},
        },
    },
}

TOOL_SEARCH = {
    "name": "purser_search",
    "description": "Search issues by text query.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search text"},
        },
        "required": ["query"],
    },
}

TOOL_DEP_ADD = {
    "name": "purser_dep_add",
    "description": "Add a dependency between two issues.",
    "parameters": {
        "type": "object",
        "properties": {
            "from_id": {"type": "string", "description": "Blocking issue ID"},
            "to_id": {"type": "string", "description": "Blocked issue ID"},
            "dep_type": {
                "type": "string",
                "enum": ["blocks", "discovered-from", "relates-to"],
                "default": "blocks",
            },
        },
        "required": ["from_id", "to_id"],
    },
}

TOOL_MEMORY_STORE = {
    "name": "purser_memory_store",
    "description": "Store a key-value pair in session memory for later retrieval.",
    "parameters": {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Memory key"},
            "value": {"type": "string", "description": "Memory value"},
            "namespace": {"type": "string", "default": "default"},
        },
        "required": ["key", "value"],
    },
}

TOOL_MEMORY_QUERY = {
    "name": "purser_memory_query",
    "description": "Search session memory by text. Returns matching entries.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Search text"},
            "limit": {"type": "integer", "default": 10},
        },
        "required": ["text"],
    },
}

TOOL_SPEC_INTAKE = {
    "name": "purser_spec_intake",
    "description": "Process a raw spec file into a structured markdown document.",
    "parameters": {
        "type": "object",
        "properties": {
            "source": {"type": "string", "description": "Path to raw spec file"},
        },
        "required": ["source"],
    },
}

TOOL_SPEC_SHOW = {
    "name": "purser_spec_show",
    "description": "Read a structured spec document by ID.",
    "parameters": {
        "type": "object",
        "properties": {
            "spec_id": {"type": "string", "description": "Spec ID"},
        },
        "required": ["spec_id"],
    },
}

TOOL_PLAN_CREATE = {
    "name": "purser_plan_create",
    "description": "Decompose a spec into epics, features, and tasks with dependencies.",
    "parameters": {
        "type": "object",
        "properties": {
            "spec_id": {"type": "string", "description": "Spec ID to decompose"},
        },
        "required": ["spec_id"],
    },
}

TOOL_PLAN_SHOW = {
    "name": "purser_plan_show",
    "description": "Show a plan's dependency tree.",
    "parameters": {
        "type": "object",
        "properties": {
            "issue_id": {"type": "string", "description": "Epic/plan issue ID"},
        },
        "required": ["issue_id"],
    },
}

TOOL_LINT = {
    "name": "purser_lint",
    "description": "Run ruff lint, ruff format, and ty type checks on the codebase. Returns structured results with pass/fail per check and error details.",
    "parameters": {
        "type": "object",
        "properties": {
            "fix": {
                "type": "boolean",
                "description": "Auto-fix lint and formatting issues where possible",
                "default": False,
            },
            "target": {
                "type": "string",
                "description": "Path to lint (default: current directory)",
                "default": ".",
            },
        },
    },
}

# --- Tool sets by role ---

ALL_TOOLS = [
    TOOL_READY,
    TOOL_CLAIM,
    TOOL_SHOW,
    TOOL_CLOSE,
    TOOL_CREATE,
    TOOL_DISCOVER,
    TOOL_NOTE,
    TOOL_LIST,
    TOOL_SEARCH,
    TOOL_DEP_ADD,
    TOOL_MEMORY_STORE,
    TOOL_MEMORY_QUERY,
    TOOL_SPEC_INTAKE,
    TOOL_SPEC_SHOW,
    TOOL_PLAN_CREATE,
    TOOL_PLAN_SHOW,
    TOOL_LINT,
]

PM_TOOLS = [
    TOOL_SHOW,
    TOOL_LIST,
    TOOL_SEARCH,
    TOOL_CREATE,
    TOOL_DEP_ADD,
    TOOL_NOTE,
    TOOL_MEMORY_STORE,
    TOOL_MEMORY_QUERY,
    TOOL_SPEC_INTAKE,
    TOOL_SPEC_SHOW,
    TOOL_PLAN_CREATE,
    TOOL_PLAN_SHOW,
]

WORKER_TOOLS = [
    TOOL_READY,
    TOOL_CLAIM,
    TOOL_SHOW,
    TOOL_CLOSE,
    TOOL_CREATE,
    TOOL_DISCOVER,
    TOOL_NOTE,
    TOOL_LIST,
    TOOL_SEARCH,
    TOOL_MEMORY_STORE,
    TOOL_MEMORY_QUERY,
    TOOL_LINT,
]


# --- Dispatch ---


def dispatch_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    memory: MemoryStore,
) -> str:
    """Execute a tool call and return the result as a string.

    This is the bridge between LLM tool calls and purser functionality.
    Returns JSON for structured data, plain text for messages.
    """
    try:
        result = _dispatch(name, arguments, memory=memory)
        if isinstance(result, str):
            return result
        if hasattr(result, "model_dump"):
            return json.dumps(result.model_dump(mode="json"), indent=2, default=str)
        if isinstance(result, list):
            items = []
            for item in result:
                if hasattr(item, "model_dump"):
                    items.append(item.model_dump(mode="json"))
                else:
                    items.append(item)
            return json.dumps(items, indent=2, default=str)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _dispatch(
    name: str,
    args: dict[str, Any],
    *,
    memory: MemoryStore,
) -> Any:
    """Internal dispatch to purser functions."""
    from pathlib import Path

    from purser import beads
    from purser.planner import create_plan
    from purser.spec import intake_spec, show_spec

    match name:
        case "purser_ready":
            return beads.ready_issues(limit=args.get("limit", 10))

        case "purser_claim":
            return beads.claim_issue(args["issue_id"])

        case "purser_show":
            return beads.show_issue(args["issue_id"])

        case "purser_close":
            return beads.close_issue(args["issue_id"], reason=args.get("reason"))

        case "purser_create":
            return beads.create_issue(
                args["title"],
                type=args.get("type", "task"),
                description=args.get("description"),
                priority=args.get("priority", 2),
                parent=args.get("parent"),
                labels=args.get("labels"),
            )

        case "purser_discover":
            issue = beads.create_issue(
                args["title"],
                type=args.get("type", "bug"),
                description=args.get("description"),
            )
            if args.get("from_issue"):
                beads.add_dependency(issue.id, args["from_issue"], dep_type="discovered-from")
            return issue

        case "purser_note":
            beads.note_issue(args["issue_id"], args["text"])
            return "Note added."

        case "purser_list":
            return beads.list_issues(**{k: v for k, v in args.items() if v is not None})

        case "purser_search":
            return beads.search_issues(args["query"])

        case "purser_dep_add":
            beads.add_dependency(
                args["from_id"],
                args["to_id"],
                dep_type=args.get("dep_type", "blocks"),
            )
            return "Dependency added."

        case "purser_memory_store":
            memory.store(
                args["key"],
                args["value"],
                namespace=args.get("namespace", "default"),
            )
            return f"Stored: {args['key']}"

        case "purser_memory_query":
            entries = memory.query(args["text"], limit=args.get("limit", 10))
            return entries

        case "purser_spec_intake":
            return intake_spec(Path(args["source"]))

        case "purser_spec_show":
            return show_spec(args["spec_id"])

        case "purser_plan_create":
            return create_plan(args["spec_id"])

        case "purser_plan_show":
            return beads.dep_tree(args["issue_id"])

        case "purser_lint":
            from purser.lint import run_lint

            return run_lint(
                target=args.get("target", "."),
                fix=args.get("fix", False),
            )

        case _:
            return {"error": f"Unknown tool: {name}"}
