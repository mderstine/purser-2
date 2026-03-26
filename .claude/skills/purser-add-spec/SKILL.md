---
name: purser-add-spec
description: Add a new spec to purser using the PM agent to synthesize structured markdown from a description. Use when the user wants to create a feature spec, PRD, or requirement document.
allowed-tools: Bash
---

# Purser Add Spec

## Instructions

1. The user provides a description or requirement for a new feature/spec.
2. Run `uv run purser spec add "<description>"` to synthesize the spec using the PM agent.
3. If the description is in a file, read it first with `Read`, then run the command.
4. Show the user the created spec ID and path.
5. Offer to show the generated spec content with `purser spec show <id>`.

## Example prompts

- "/purser-add-spec Build a user authentication system with OAuth2 and session management"
- "/purser-add-spec Create a PRD for the new dashboard feature with real-time analytics"
- "/purser-add-spec File upload service supporting S3 and local storage with validation"

## Output

Reports the created spec ID, title, and file path.
