---
id: spec-migrate-to-claude-code-channels
title: Migrate to claude-code-channels for Discord Integration
created: 2026-03-26
source: inline
---

# Migrate to claude-code-channels for Discord Integration

## Problem Statement

The current custom Discord bot implementation in `discord_bot/` is project-specific and tightly coupled to the purser framework. This creates maintenance overhead and doesn't leverage the community-supported `claude-code-channels` tool. We need to remove the custom implementation and migrate to using the standard `claude-code-channels` package which provides better Discord integration with Claude Code.

## Goals

- Remove the custom `discord_bot/` directory and all its code
- Document how to install and configure `claude-code-channels`
- Ensure existing purser functionality works without the Discord bot
- Provide clear migration path for users who were using the custom bot

## Non-Goals

- Re-implementing claude-code-channels features
- Maintaining the custom bot as an alternative
- Modifying the claude-code-channels package itself

## User Stories

- As a user, I can install claude-code-channels via pip and configure it for my Claude Code sessions
- As a user, I understand why the custom bot was removed and what replaces it
- As a developer, the purser codebase is cleaner without the Discord-specific code
- As a user, I can still use purser for project management without Discord integration

## Technical Constraints

- Python 3.10+
- claude-code-channels is installed as a separate tool (not a dependency)
- No breaking changes to core purser functionality
- Clean removal - no leftover references

## Acceptance Criteria

- [ ] `discord_bot/` directory is completely removed
- [ ] All Discord-related dependencies removed from pyproject.toml
- [ ] Documentation added explaining how to use claude-code-channels
- [ ] Any references to Discord in AGENTS.md or other docs are updated
- [ ] Test that purser commands still work without Discord components

## Open Questions

- Should we keep any Discord-related configuration examples?
- Do we need a migration guide for users who were using the custom bot?
- Should we add claude-code-channels as an optional dependency or just document it?
