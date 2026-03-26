---
name: init-purser
description: Initialize purser project management framework in the current directory. Sets up beads, DuckDB memory, and directory structure. Use when starting a new project or checking purser status.
allowed-tools: Bash
---

# Init Purser

## Instructions

1. Run `./scripts/init-purser` to initialize purser with full diagnostics.
2. If the user wants to check status without modifying, use `./scripts/init-purser --check`.
3. If the user wants to force re-initialization, use `./scripts/init-purser --force`.
4. Report the initialization status including memory DB, specs directory, formulas directory, and beads CLI.

## Example prompts

- "/purser-init"
- "/purser-init Check if purser is set up"
- "/purser-init Force reinitialize the project"

## Output

Shows initialization progress and final status. If AGENTS.md doesn't exist, it will be created with a template.
